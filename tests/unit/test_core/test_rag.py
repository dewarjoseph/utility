"""Tests for the RAG pipeline module."""

import pytest
from core.rag import (
    RAGPipeline, Document, DocumentChunk, DocumentType,
    TextChunker, SimpleVectorStore, MockEmbedder,
    SAMPLE_ZONING_CODE, get_rag_pipeline
)


class TestTextChunker:
    """Tests for text chunking."""

    def test_chunk_small_text(self):
        chunker = TextChunker(chunk_size=100)
        doc = Document(
            id="test",
            title="Test",
            doc_type=DocumentType.ZONING_CODE,
            source_url=None,
            jurisdiction="Test City",
            content="This is a short piece of text."
        )
        
        chunks = chunker.chunk_document(doc)
        assert len(chunks) >= 1

    def test_chunk_with_sections(self):
        chunker = TextChunker(respect_sections=True)
        doc = Document(
            id="test",
            title="Zoning Code",
            doc_type=DocumentType.ZONING_CODE,
            source_url=None,
            jurisdiction="Test City",
            content=SAMPLE_ZONING_CODE
        )
        
        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 1
        # Check that section paths are captured
        assert any(c.section_path for c in chunks)

    def test_chunk_overlap(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        long_text = " ".join(["word"] * 200)
        doc = Document(
            id="test",
            title="Test",
            doc_type=DocumentType.ORDINANCE,
            source_url=None,
            jurisdiction="Test",
            content=long_text
        )
        
        chunks = chunker.chunk_document(doc)
        assert len(chunks) > 3


class TestMockEmbedder:
    """Tests for mock embedder."""

    def test_embed_dimension(self):
        embedder = MockEmbedder(dimension=384)
        embedding = embedder.embed("test text")
        assert len(embedding) == 384

    def test_embed_deterministic(self):
        embedder = MockEmbedder()
        e1 = embedder.embed("hello world")
        e2 = embedder.embed("hello world")
        assert e1 == e2

    def test_embed_batch(self):
        embedder = MockEmbedder()
        embeddings = embedder.embed_batch(["text1", "text2", "text3"])
        assert len(embeddings) == 3


class TestSimpleVectorStore:
    """Tests for vector store."""

    def test_add_and_search(self):
        store = SimpleVectorStore()
        embedder = MockEmbedder()
        
        chunk = DocumentChunk(
            id="c1",
            document_id="d1",
            content="This is about zoning regulations",
            metadata={},
        )
        embedding = embedder.embed(chunk.content)
        store.add_chunk(chunk, embedding)
        
        query_embedding = embedder.embed("zoning rules")
        results = store.search(query_embedding, top_k=1)
        
        assert len(results) == 1
        assert results[0].chunk.id == "c1"


class TestRAGPipeline:
    """Tests for the complete RAG pipeline."""

    def test_ingest_document(self):
        pipeline = RAGPipeline()
        doc = Document(
            id="zoning_code",
            title="Sample Zoning Code",
            doc_type=DocumentType.ZONING_CODE,
            source_url=None,
            jurisdiction="Sample City",
            content=SAMPLE_ZONING_CODE
        )
        
        chunk_count = pipeline.ingest_document(doc)
        assert chunk_count > 0
        assert "zoning_code" in pipeline.documents

    def test_query(self):
        pipeline = RAGPipeline()
        doc = Document(
            id="zoning_code",
            title="Sample Zoning Code",
            doc_type=DocumentType.ZONING_CODE,
            source_url=None,
            jurisdiction="Sample City",
            content=SAMPLE_ZONING_CODE
        )
        pipeline.ingest_document(doc)
        
        results = pipeline.query("What is the maximum height in R-1?", top_k=3)
        assert len(results) > 0

    def test_format_context(self):
        pipeline = RAGPipeline()
        doc = Document(
            id="zoning_code",
            title="Sample Zoning Code",
            doc_type=DocumentType.ZONING_CODE,
            source_url=None,
            jurisdiction="Sample City",
            content=SAMPLE_ZONING_CODE
        )
        pipeline.ingest_document(doc)
        
        results = pipeline.query("ADU requirements", top_k=2)
        context = pipeline.format_context(results)
        
        assert "[Source" in context

    def test_get_stats(self):
        pipeline = RAGPipeline()
        doc = Document(
            id="test",
            title="Test",
            doc_type=DocumentType.ZONING_CODE,
            source_url=None,
            jurisdiction="Test City",
            content=SAMPLE_ZONING_CODE
        )
        pipeline.ingest_document(doc)
        
        stats = pipeline.get_stats()
        assert stats['documents'] == 1
        assert stats['chunks'] > 0


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_rag_pipeline(self):
        pipeline = get_rag_pipeline()
        assert isinstance(pipeline, RAGPipeline)
