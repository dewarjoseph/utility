"""
RAG Pipeline Module - Retrieval-Augmented Generation for municipal codes.

Provides document ingestion, chunking, vector storage, and retrieval
for zoning ordinances and municipal regulations.
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import math


class DocumentType(Enum):
    """Type of legal document."""
    ZONING_CODE = "zoning_code"
    BUILDING_CODE = "building_code"
    SUBDIVISION = "subdivision"
    GENERAL_PLAN = "general_plan"
    ORDINANCE = "ordinance"


@dataclass
class DocumentChunk:
    """A chunk of a document for vector storage."""
    id: str
    document_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    
    # Hierarchical references
    parent_id: Optional[str] = None
    section_path: str = ""  # e.g., "Chapter 12 > Article 4 > Section 12.04"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'document_id': self.document_id,
            'content': self.content[:200] + "..." if len(self.content) > 200 else self.content,
            'section_path': self.section_path,
            'metadata': self.metadata,
        }


@dataclass
class Document:
    """A full document in the RAG system."""
    id: str
    title: str
    doc_type: DocumentType
    source_url: Optional[str]
    jurisdiction: str
    content: str
    chunks: List[DocumentChunk] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'type': self.doc_type.value,
            'jurisdiction': self.jurisdiction,
            'chunk_count': len(self.chunks),
        }


@dataclass
class RetrievalResult:
    """Result of a retrieval query."""
    chunk: DocumentChunk
    score: float
    parent_content: Optional[str] = None


class TextChunker:
    """Chunks documents with hierarchical awareness."""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        respect_sections: bool = True
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.respect_sections = respect_sections
    
    def chunk_document(self, doc: Document) -> List[DocumentChunk]:
        """Chunk a document into searchable pieces."""
        chunks = []
        
        if self.respect_sections:
            # Parse sections from legal document
            sections = self._parse_sections(doc.content)
            
            for section_path, section_content in sections:
                section_chunks = self._chunk_text(
                    section_content,
                    doc.id,
                    section_path
                )
                chunks.extend(section_chunks)
        else:
            chunks = self._chunk_text(doc.content, doc.id, "")
        
        return chunks
    
    def _parse_sections(self, content: str) -> List[Tuple[str, str]]:
        """Parse hierarchical sections from legal text."""
        sections = []
        
        # Common patterns for legal document sections
        patterns = [
            r'(Chapter\s+\d+[A-Z]?[\.\s]+[^\n]+)',
            r'(Article\s+\d+[A-Z]?[\.\s]+[^\n]+)',
            r'(Section\s+\d+[\.\d]*[\.\s]+[^\n]+)',
            r'(§\s*\d+[\.\d]*[^\n]+)',
        ]
        
        # Find all section headers
        combined_pattern = '|'.join(f'({p})' for p in patterns)
        matches = list(re.finditer(combined_pattern, content, re.IGNORECASE))
        
        if not matches:
            # No sections found, return entire content
            return [("Document", content)]
        
        # Extract content between sections
        for i, match in enumerate(matches):
            section_title = match.group(0).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_content = content[start:end].strip()
            
            if section_content:
                sections.append((section_title, section_content))
        
        return sections if sections else [("Document", content)]
    
    def _chunk_text(
        self,
        text: str,
        doc_id: str,
        section_path: str
    ) -> List[DocumentChunk]:
        """Chunk text into overlapping pieces."""
        chunks = []
        words = text.split()
        
        if len(words) <= self.chunk_size:
            # Small enough, single chunk
            chunk_id = hashlib.md5(f"{doc_id}:{section_path}:0".encode()).hexdigest()[:12]
            chunks.append(DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                content=text,
                metadata={'word_count': len(words)},
                section_path=section_path,
            ))
        else:
            # Split into overlapping chunks
            i = 0
            chunk_num = 0
            while i < len(words):
                chunk_words = words[i:i + self.chunk_size]
                chunk_text = ' '.join(chunk_words)
                
                chunk_id = hashlib.md5(
                    f"{doc_id}:{section_path}:{chunk_num}".encode()
                ).hexdigest()[:12]
                
                chunks.append(DocumentChunk(
                    id=chunk_id,
                    document_id=doc_id,
                    content=chunk_text,
                    metadata={
                        'word_count': len(chunk_words),
                        'chunk_num': chunk_num,
                    },
                    section_path=section_path,
                ))
                
                i += self.chunk_size - self.chunk_overlap
                chunk_num += 1
        
        return chunks


class SimpleVectorStore:
    """Simple in-memory vector store using cosine similarity.
    
    For production, replace with Pinecone, pgvector, or similar.
    """
    
    def __init__(self):
        self.chunks: Dict[str, DocumentChunk] = {}
        self.embeddings: Dict[str, List[float]] = {}
    
    def add_chunk(self, chunk: DocumentChunk, embedding: List[float]):
        """Add a chunk with its embedding."""
        self.chunks[chunk.id] = chunk
        self.embeddings[chunk.id] = embedding
        chunk.embedding = embedding
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_doc_type: Optional[DocumentType] = None
    ) -> List[RetrievalResult]:
        """Search for similar chunks."""
        results = []
        
        for chunk_id, chunk in self.chunks.items():
            if filter_doc_type and chunk.metadata.get('doc_type') != filter_doc_type.value:
                continue
            
            embedding = self.embeddings.get(chunk_id)
            if embedding:
                score = self._cosine_similarity(query_embedding, embedding)
                results.append(RetrievalResult(chunk=chunk, score=score))
        
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)


class MockEmbedder:
    """Mock embedder for development. Replace with OpenAI/Cohere in production."""
    
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
    
    def embed(self, text: str) -> List[float]:
        """Generate a mock embedding based on text hash."""
        # Create deterministic pseudo-random embedding from text
        text_hash = hashlib.sha256(text.lower().encode()).digest()
        
        # Convert bytes to floats in [-1, 1] range
        embedding = []
        for i in range(self.dimension):
            byte_val = text_hash[i % len(text_hash)]
            embedding.append((byte_val / 127.5) - 1.0)
        
        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        return [x / norm for x in embedding]
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        return [self.embed(text) for text in texts]


class RAGPipeline:
    """Complete RAG pipeline for municipal code queries."""
    
    def __init__(self):
        self.chunker = TextChunker()
        self.vector_store = SimpleVectorStore()
        self.embedder = MockEmbedder()
        self.documents: Dict[str, Document] = {}
    
    def ingest_document(self, doc: Document) -> int:
        """Ingest a document into the RAG system."""
        # Chunk the document
        chunks = self.chunker.chunk_document(doc)
        doc.chunks = chunks
        self.documents[doc.id] = doc
        
        # Embed and store each chunk
        for chunk in chunks:
            chunk.metadata['doc_type'] = doc.doc_type.value
            chunk.metadata['jurisdiction'] = doc.jurisdiction
            
            embedding = self.embedder.embed(chunk.content)
            self.vector_store.add_chunk(chunk, embedding)
        
        return len(chunks)
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        include_parent: bool = True
    ) -> List[RetrievalResult]:
        """Query the RAG system."""
        query_embedding = self.embedder.embed(question)
        results = self.vector_store.search(query_embedding, top_k=top_k)
        
        if include_parent:
            # Fetch parent section content for context
            for result in results:
                if result.chunk.section_path:
                    # Find all chunks in same section
                    section_chunks = [
                        c for c in self.vector_store.chunks.values()
                        if c.section_path == result.chunk.section_path
                    ]
                    if section_chunks:
                        result.parent_content = '\n'.join(
                            c.content for c in sorted(
                                section_chunks,
                                key=lambda c: c.metadata.get('chunk_num', 0)
                            )
                        )
        
        return results
    
    def format_context(self, results: List[RetrievalResult]) -> str:
        """Format retrieval results as context for LLM."""
        context_parts = []
        
        for i, result in enumerate(results, 1):
            chunk = result.chunk
            section = chunk.section_path or "General"
            
            context_parts.append(
                f"[Source {i}: {section}]\n{chunk.content}"
            )
        
        return "\n\n---\n\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return {
            'documents': len(self.documents),
            'chunks': len(self.vector_store.chunks),
            'jurisdictions': list(set(
                d.jurisdiction for d in self.documents.values()
            )),
        }


def get_rag_pipeline() -> RAGPipeline:
    """Factory function for RAG pipeline."""
    return RAGPipeline()


# Sample municipal code for testing
SAMPLE_ZONING_CODE = """
Chapter 12 - ZONING REGULATIONS

Article 1. General Provisions

Section 12.01. Purpose
The purpose of this chapter is to promote the public health, safety, and general 
welfare by regulating the use of land and buildings. These regulations are designed 
to secure adequate light, air, and open space; to prevent overcrowding and undue 
concentration of population; and to facilitate adequate provision for transportation, 
water, sewage, schools, parks, and other public requirements.

Section 12.02. Definitions
For the purposes of this chapter, the following terms shall have the meanings ascribed:
- "Accessory Dwelling Unit (ADU)" means a secondary residential unit on a lot with a primary dwelling.
- "Building Height" means the vertical distance from the average grade to the highest point of the roof.
- "Floor Area Ratio (FAR)" means the ratio of gross floor area to lot area.
- "Lot Coverage" means the percentage of a lot covered by buildings and structures.

Article 2. Residential Districts

Section 12.10. R-1 Single Family Residential
The R-1 district is intended for low-density single-family residential development.
- Minimum lot size: 6,000 square feet
- Maximum building height: 30 feet
- Maximum lot coverage: 40%
- Front setback: 20 feet
- Side setback: 5 feet
- Rear setback: 15 feet

Section 12.11. R-2 Two-Family Residential
The R-2 district allows for duplexes and single-family homes.
- Minimum lot size: 5,000 square feet per unit
- Maximum building height: 35 feet
- Maximum lot coverage: 45%
- Maximum FAR: 0.6

Section 12.12. R-3 Multi-Family Residential
The R-3 district accommodates apartments and condominiums.
- Minimum lot size: 3,000 square feet per unit
- Maximum building height: 45 feet
- Maximum lot coverage: 50%
- Maximum FAR: 1.5
- Parking requirement: 1.5 spaces per unit

Article 3. Commercial Districts

Section 12.20. C-1 Neighborhood Commercial
Intended for small-scale retail and service uses serving the immediate neighborhood.
- Permitted uses: Retail stores under 5,000 sq ft, restaurants, personal services
- Prohibited uses: Drive-through facilities, auto repair
- Maximum building height: 35 feet

Section 12.21. C-2 Community Commercial
For larger commercial uses serving a wider area.
- Permitted uses: Retail, office, entertainment, hotels
- Maximum building height: 55 feet
- Maximum FAR: 2.0
- Parking: Per use category in Section 12.50

Article 4. Special Provisions

Section 12.40. Accessory Dwelling Units
ADUs are permitted by right in all residential zones subject to:
- Maximum size: 1,200 square feet or 50% of primary dwelling, whichever is less
- Owner occupancy: Not required
- Parking: None required within 0.5 mile of transit
- Setbacks: 4 feet from side and rear property lines

Section 12.41. Community Land Trusts
Properties held by qualified Community Land Trusts may receive:
- Density bonus of 25%
- Reduced parking requirements (50% of standard)
- Expedited permit processing
- Fee waivers for affordable units
"""
