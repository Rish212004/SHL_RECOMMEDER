"""
Retrieval Engine
================
YEH FILE KYA KARTI HAI:
- Catalog ko embed karke vector store mein daalti hai (FAISS)
- Jab agent ko assessments dhundhne hote hain, yeh engine relevant ones return karti hai
- Hybrid search: TF-IDF + keyword matching (simple aur reliable)

KYUN FAISS NAHI:
- Free tier mein numpy+sklearn kaafi hai
- FAISS install karna sometimes tricky hota hai deployment pe
- Sentence transformers bhi heavy hain cold start ke liye
- isliye TF-IDF use kiya - lightweight, fast, interpretable

KYUN HYBRID SEARCH:
- Pure semantic: "Python developer" se "scripting" nahi milta always
- Pure keyword: context miss ho jaata hai
- Hybrid dono ka best deta hai
"""

import json
import re
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter
import logging
import os

logger = logging.getLogger(__name__)


class CatalogRetriever:
    """
    SHL Catalog ka retrieval engine.
    TF-IDF based similarity + keyword boosting use karta hai.
    """
    
    def __init__(self, catalog_path: str = None):
        self.catalog = []
        self.tfidf_matrix = []
        self.vocab = {}
        self._load_and_index(catalog_path)
    
    def _load_and_index(self, catalog_path: Optional[str] = None):
        """Catalog load karo aur index banao"""
        # Catalog load karo
        if catalog_path and os.path.exists(catalog_path):
            with open(catalog_path, 'r') as f:
                self.catalog = json.load(f)
        else:
            # Fallback: scraper se import karo
            from catalog.scraper import SHL_CATALOG
            self.catalog = SHL_CATALOG
        
        logger.info(f"Loaded {len(self.catalog)} assessments")
        
        # TF-IDF index banao
        self._build_tfidf_index()
    
    def _tokenize(self, text: str) -> List[str]:
        """Text ko tokens mein todna"""
        text = text.lower()
        # Special chars remove karo
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        tokens = text.split()
        # Common stop words remove karo
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'be', 'to', 'of', 
                      'and', 'or', 'in', 'for', 'with', 'on', 'at', 'by', 'from',
                      'i', 'we', 'you', 'they', 'it', 'this', 'that', 'what',
                      'who', 'how', 'when', 'where', 'which', 'who', 'need',
                      'want', 'hiring', 'hire', 'looking', 'help', 'please',
                      'can', 'could', 'would', 'should', 'will', 'have', 'has'}
        return [t for t in tokens if t not in stop_words and len(t) > 1]
    
    def _get_document_text(self, assessment: dict) -> str:
        """Assessment ko searchable text mein convert karo"""
        parts = [
            assessment.get('name', ''),
            assessment.get('description', ''),
            assessment.get('test_type_full', ''),
            ' '.join(assessment.get('skills', [])),
            ' '.join(assessment.get('job_levels', [])),
        ]
        return ' '.join(parts)
    
    def _build_tfidf_index(self):
        """TF-IDF matrix banao catalog ke liye"""
        # Sabse pehle corpus build karo
        corpus = []
        for assessment in self.catalog:
            doc_text = self._get_document_text(assessment)
            tokens = self._tokenize(doc_text)
            corpus.append(tokens)
        
        # Vocabulary banao (IDF ke liye)
        doc_freq = Counter()
        for tokens in corpus:
            for token in set(tokens):
                doc_freq[token] += 1
        
        # Sirf wo tokens rakhte hain jo >=1 documents mein aate hain
        N = len(corpus)
        self.vocab = {
            word: idx for idx, (word, _) in 
            enumerate(doc_freq.most_common())
        }
        
        # TF-IDF vectors compute karo
        self.tfidf_matrix = []
        for tokens in corpus:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vec = {}
            for token, count in tf.items():
                if token in self.vocab:
                    # TF = term frequency
                    tf_score = count / total
                    # IDF = inverse document frequency
                    idf_score = math.log(N / (doc_freq[token] + 1)) + 1
                    vec[token] = tf_score * idf_score
            self.tfidf_matrix.append(vec)
        
        logger.info(f"TF-IDF index built: vocab size={len(self.vocab)}")
    
    def _cosine_similarity(self, vec1: dict, vec2: dict) -> float:
        """Do vectors ke beech cosine similarity calculate karo"""
        if not vec1 or not vec2:
            return 0.0
        
        # Dot product
        dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in vec2)
        
        # Magnitudes
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot / (mag1 * mag2)
    
    def _query_to_vec(self, query: str) -> dict:
        """Query ko TF-IDF vector mein convert karo"""
        tokens = self._tokenize(query)
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        N = len(self.catalog)
        
        vec = {}
        for token, count in tf.items():
            if token in self.vocab:
                tf_score = count / total
                # Query ke liye simple IDF (approximate)
                vec[token] = tf_score * 2.0  # Boost query terms
        
        return vec
    
    def _keyword_boost(self, assessment: dict, query: str) -> float:
        """
        Direct keyword matches ke liye extra score deta hai.
        Jaise 'java' query mein Java assessment ko zyada score milega.
        """
        query_lower = query.lower()
        boost = 0.0
        
        # Name match - sabse important
        name_lower = assessment['name'].lower()
        words = query_lower.split()
        for word in words:
            if len(word) > 2 and word in name_lower:
                boost += 0.3
        
        # Skill match
        for skill in assessment.get('skills', []):
            if skill.lower() in query_lower:
                boost += 0.2
        
        # Test type mention
        query_has_personality = any(w in query_lower for w in 
                                   ['personality', 'behavior', 'behaviour', 'trait', 'opq'])
        query_has_ability = any(w in query_lower for w in 
                               ['aptitude', 'reasoning', 'cognitive', 'numerical', 'verbal'])
        query_has_knowledge = any(w in query_lower for w in 
                                  ['knowledge', 'skill', 'technical', 'programming', 'coding'])
        
        if query_has_personality and assessment['test_type'] == 'P':
            boost += 0.4
        if query_has_ability and assessment['test_type'] == 'A':
            boost += 0.3
        if query_has_knowledge and assessment['test_type'] == 'K':
            boost += 0.3
        
        return boost
    
    def search(self, query: str, top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """
        Main search function.
        
        Args:
            query: User ki query ya collected context
            top_k: Kitne results chahiye (max 10)
            filters: Optional filters like test_type, job_level
        
        Returns:
            List of matching assessments with scores
        """
        query_vec = self._query_to_vec(query)
        
        scored = []
        for idx, (assessment, doc_vec) in enumerate(zip(self.catalog, self.tfidf_matrix)):
            # Filter apply karo pehle
            if filters:
                if 'test_type' in filters and filters['test_type']:
                    if assessment['test_type'] not in filters['test_type']:
                        continue
            
            # Cosine similarity
            base_score = self._cosine_similarity(query_vec, doc_vec)
            
            # Keyword boost
            keyword_score = self._keyword_boost(assessment, query)
            
            # Final score
            final_score = base_score + keyword_score
            
            if final_score > 0:
                scored.append({
                    'assessment': assessment,
                    'score': final_score
                })
        
        # Sort by score
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        # Top K return karo
        results = []
        for item in scored[:top_k]:
            result = item['assessment'].copy()
            result['_relevance_score'] = round(item['score'], 3)
            results.append(result)
        
        return results
    
    def get_by_name(self, name: str) -> Optional[Dict]:
        """Name se exact assessment dhundho (comparison ke liye)"""
        name_lower = name.lower()
        for assessment in self.catalog:
            if (assessment['name'].lower() == name_lower or 
                name_lower in assessment['name'].lower()):
                return assessment
        return None
    
    def get_all_names(self) -> List[str]:
        """Saare assessment names return karo"""
        return [a['name'] for a in self.catalog]
    
    def get_catalog_summary(self) -> str:
        """Agent ke liye catalog summary banao"""
        types = {}
        for a in self.catalog:
            t = a['test_type_full']
            types[t] = types.get(t, 0) + 1
        
        summary = f"SHL Individual Test Solutions Catalog ({len(self.catalog)} assessments):\n"
        for test_type, count in types.items():
            summary += f"- {test_type}: {count} assessments\n"
        
        return summary


# Global retriever instance (singleton pattern - ek baar banao, baar baar use karo)
_retriever_instance = None

def get_retriever() -> CatalogRetriever:
    """Singleton retriever return karo"""
    global _retriever_instance
    if _retriever_instance is None:
        catalog_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            'catalog', 'catalog.json'
        )
        _retriever_instance = CatalogRetriever(catalog_path)
    return _retriever_instance