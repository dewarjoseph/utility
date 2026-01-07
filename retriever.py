import math
import re
from collections import Counter
from typing import List, Dict, Tuple
from analyzer import Property

class VectorSearch:
    def __init__(self):
        self.corpus_size = 0
        self.tf_idf_vectors = []
        self.properties = []
        self.idf: Dict[str, float] = {}
        self.vocabulary: set = set()

    def _tokenize(self, text: str) -> List[str]:
        # Simple consistent tokenization
        text = text.lower()
        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()

    def fit(self, properties: List[Property]):
        self.properties = properties
        self.corpus_size = len(properties)
        
        # 1. Term Frequency (TF) per document
        doc_term_freqs = []
        doc_frequencies = Counter() # How many docs contain a word

        for p in properties:
            tokens = self._tokenize(p.description)
            tf = Counter(tokens)
            doc_term_freqs.append(tf)
            self.vocabulary.update(tokens)
            
            # Count presence (unique words per doc) for IDF
            for token in set(tokens):
                doc_frequencies[token] += 1
        
        # 2. Inverse Document Frequency (IDF)
        # IDF(t) = log(N / (df(t) + 1))
        for token in self.vocabulary:
            self.idf[token] = math.log(self.corpus_size / (doc_frequencies[token] + 1))

        # 3. Create Vectors
        self.tf_idf_vectors = []
        for tf in doc_term_freqs:
            vec = self._compute_vector(tf)
            self.tf_idf_vectors.append(vec)

    def _compute_vector(self, tf: Counter) -> Dict[str, float]:
        # Calculate TF-IDF vector for a set of term frequencies
        # Length normalization (making it a unit vector) for Cosine Similarity
        vec = {}
        total_terms = sum(tf.values())
        if total_terms == 0:
             return {}
        
        norm = 0.0
        for token in tf:
            # TF = count / total_words (normalized TF)
            val = (tf[token] / total_terms) * self.idf.get(token, 0)
            vec[token] = val
            norm += val * val
        
        # Normalize
        norm = math.sqrt(norm)
        if norm > 0:
            for token in vec:
                vec[token] /= norm
        
        return vec

    def search(self, query: str, top_k: int = 5) -> List[Property]:
        tokens = self._tokenize(query)
        query_tf = Counter(tokens)
        query_vec = self._compute_vector(query_tf)

        scores: List[Tuple[float, Property]] = []

        for i, doc_vec in enumerate(self.tf_idf_vectors):
            # Dot product for Cosine Similarity (vectors are already unit vectors)
            score = 0.0
            for token, val in query_vec.items():
                if token in doc_vec:
                    score += val * doc_vec[token]
            
            if score > 0:
                scores.append((score, self.properties[i]))
        
        # Sort desc
        scores.sort(key=lambda x: x[0], reverse=True)
        
        return [item[1] for item in scores[:top_k]]
