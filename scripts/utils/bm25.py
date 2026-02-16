#!/usr/bin/env python3
"""
Pure Python BM25 implementation for Second Brain v2

Provides text search functionality when qmd is not available.
"""

import math
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set
import string


class BM25Searcher:
    """BM25 text search implementation."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 searcher.
        
        Args:
            k1: Controls term frequency normalization (typically 1.2-2.0)
            b: Controls document length normalization (typically 0.75)
        """
        self.k1 = k1
        self.b = b
        
        # Document storage
        self.documents = []  # List of (doc_id, content, metadata)
        self.doc_lengths = []  # Document lengths
        self.avg_doc_length = 0.0
        
        # Inverted index: term -> [(doc_idx, term_freq), ...]
        self.inverted_index = defaultdict(list)
        
        # Document frequency: term -> num_docs_containing_term
        self.doc_frequencies = Counter()
        
        # Total number of documents
        self.num_docs = 0
        
        # Stop words
        self.stop_words = self._get_stop_words()
    
    def _get_stop_words(self) -> Set[str]:
        """Get common English stop words."""
        return {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'their', 'our'
        }
    
    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text)
        tokens = text.split()
        
        # Remove stop words and empty tokens
        tokens = [
            token for token in tokens 
            if token and token not in self.stop_words and len(token) > 1
        ]
        
        return tokens
    
    def add_document(self, doc_id: str, content: str, metadata: Dict = None) -> None:
        """Add a document to the search index."""
        if metadata is None:
            metadata = {}
        
        # Tokenize content
        tokens = self.tokenize(content)
        doc_length = len(tokens)
        
        # Store document
        doc_idx = len(self.documents)
        self.documents.append((doc_id, content, metadata))
        self.doc_lengths.append(doc_length)
        
        # Update inverted index
        term_freqs = Counter(tokens)
        for term, freq in term_freqs.items():
            self.inverted_index[term].append((doc_idx, freq))
            if freq > 0:  # Document contains this term
                self.doc_frequencies[term] += 1
        
        # Update statistics
        self.num_docs += 1
        self.avg_doc_length = sum(self.doc_lengths) / self.num_docs
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search for documents matching the query.
        
        Args:
            query: Search query string
            limit: Maximum number of results
        
        Returns:
            List of dicts with doc_id, content, metadata, score, and highlights
        """
        if not self.documents:
            return []
        
        query_terms = self.tokenize(query)
        if not query_terms:
            return []
        
        # Calculate BM25 scores for all documents
        doc_scores = [0.0] * self.num_docs
        
        for term in query_terms:
            if term not in self.inverted_index:
                continue
            
            # Document frequency for this term
            df = self.doc_frequencies[term]
            if df == 0:
                continue
            
            # IDF component
            idf = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1.0)
            
            # Add to document scores
            for doc_idx, term_freq in self.inverted_index[term]:
                # TF component with normalization
                tf_component = (term_freq * (self.k1 + 1)) / (
                    term_freq + self.k1 * (1 - self.b + self.b * 
                    (self.doc_lengths[doc_idx] / self.avg_doc_length))
                )
                
                doc_scores[doc_idx] += idf * tf_component
        
        # Get top results
        doc_score_pairs = [
            (i, score) for i, score in enumerate(doc_scores) 
            if score > 0
        ]
        doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
        
        # Format results
        results = []
        for doc_idx, score in doc_score_pairs[:limit]:
            doc_id, content, metadata = self.documents[doc_idx]
            
            # Generate highlights
            highlights = self._generate_highlights(content, query_terms)
            
            results.append({
                'doc_id': doc_id,
                'content': content,
                'metadata': metadata,
                'score': score,
                'highlights': highlights
            })
        
        return results
    
    def _generate_highlights(self, content: str, query_terms: List[str]) -> List[str]:
        """Generate highlighted snippets from content."""
        content_lower = content.lower()
        highlights = []
        
        for term in query_terms:
            # Find term positions
            positions = []
            start = 0
            while True:
                pos = content_lower.find(term, start)
                if pos == -1:
                    break
                positions.append(pos)
                start = pos + 1
            
            # Create highlights with context
            for pos in positions[:3]:  # Max 3 highlights per term
                start = max(0, pos - 50)
                end = min(len(content), pos + len(term) + 50)
                
                snippet = content[start:end]
                
                # Highlight the term (simple approach)
                term_start = pos - start
                term_end = term_start + len(term)
                highlighted = (
                    snippet[:term_start] + 
                    f"**{snippet[term_start:term_end]}**" + 
                    snippet[term_end:]
                )
                
                highlights.append(highlighted.strip())
        
        return highlights[:5]  # Max 5 total highlights
    
    def get_stats(self) -> Dict:
        """Get search index statistics."""
        return {
            'num_documents': self.num_docs,
            'avg_doc_length': self.avg_doc_length,
            'total_terms': len(self.inverted_index),
            'total_tokens': sum(self.doc_lengths)
        }


def create_memory_search_index(memory_files: List[Dict]) -> BM25Searcher:
    """Create a BM25 search index from memory files."""
    searcher = BM25Searcher()
    
    for memory_file in memory_files:
        doc_id = memory_file.get('path', 'unknown')
        content = memory_file.get('content', '')
        
        # Extract metadata
        metadata = {
            'path': memory_file.get('path'),
            'size': memory_file.get('size', 0),
            'modified': memory_file.get('modified'),
            'sections': memory_file.get('sections', {})
        }
        
        # Add sections as separate searchable content
        sections = memory_file.get('sections', {})
        if sections:
            # Combine all section content
            section_content = []
            for section_name, items in sections.items():
                section_content.append(f"## {section_name}")
                section_content.extend(f"- {item}" for item in items)
            
            combined_content = content + "\n\n" + "\n".join(section_content)
        else:
            combined_content = content
        
        searcher.add_document(doc_id, combined_content, metadata)
    
    return searcher