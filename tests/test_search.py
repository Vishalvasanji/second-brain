#!/usr/bin/env python3
"""
Unit tests for memory search functionality.
"""

import unittest
from pathlib import Path
import sys

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

from utils.bm25 import BM25Searcher, create_memory_search_index


class TestBM25Searcher(unittest.TestCase):
    """Test BM25 search implementation."""
    
    def setUp(self):
        """Set up test searcher with sample documents."""
        self.searcher = BM25Searcher()
        
        # Add sample documents
        self.sample_docs = [
            {
                'id': 'doc1',
                'content': 'Claude is an AI assistant created by Anthropic. Claude can help with coding, writing, and analysis.',
                'metadata': {'source': 'test1'}
            },
            {
                'id': 'doc2', 
                'content': 'Python is a programming language. Python is great for machine learning and data analysis.',
                'metadata': {'source': 'test2'}
            },
            {
                'id': 'doc3',
                'content': 'OpenClaw is a framework for AI agents. Agents can remember information across sessions.',
                'metadata': {'source': 'test3'}
            },
            {
                'id': 'doc4',
                'content': 'The second brain system helps organize memories. Memories are extracted from session logs.',
                'metadata': {'source': 'test4'}
            }
        ]
        
        for doc in self.sample_docs:
            self.searcher.add_document(doc['id'], doc['content'], doc['metadata'])
    
    def test_tokenization(self):
        """Test text tokenization."""
        text = "The quick brown fox jumps over the lazy dog!"
        tokens = self.searcher.tokenize(text)
        
        # Should remove stop words and punctuation
        expected = ['quick', 'brown', 'fox', 'jumps', 'over', 'lazy', 'dog']
        self.assertEqual(tokens, expected)
    
    def test_basic_search(self):
        """Test basic search functionality."""
        results = self.searcher.search("Claude AI assistant")
        
        # Should find doc1 which mentions Claude
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['doc_id'], 'doc1')
        self.assertGreater(results[0]['score'], 0)
    
    def test_search_relevance_ranking(self):
        """Test that results are ranked by relevance."""
        results = self.searcher.search("Python programming")
        
        # Should find doc2 first (mentions Python twice)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['doc_id'], 'doc2')
        
        # First result should have higher score than others
        if len(results) > 1:
            self.assertGreater(results[0]['score'], results[1]['score'])
    
    def test_search_with_limit(self):
        """Test search result limiting."""
        results = self.searcher.search("system", limit=2)
        
        # Should return at most 2 results
        self.assertLessEqual(len(results), 2)
    
    def test_search_no_results(self):
        """Test search with no matching documents."""
        results = self.searcher.search("quantum physics blockchain")
        
        # Should return empty list for terms not in corpus
        self.assertEqual(len(results), 0)
    
    def test_highlights_generation(self):
        """Test search result highlights."""
        results = self.searcher.search("Claude assistant")
        
        if results:
            highlights = results[0]['highlights']
            self.assertIsInstance(highlights, list)
            
            # Highlights should contain search terms
            highlight_text = ' '.join(highlights).lower()
            self.assertIn('claude', highlight_text)
    
    def test_search_stats(self):
        """Test search index statistics."""
        stats = self.searcher.get_stats()
        
        self.assertEqual(stats['num_documents'], 4)
        self.assertGreater(stats['total_terms'], 0)
        self.assertGreater(stats['avg_doc_length'], 0)


class TestMemorySearchIndex(unittest.TestCase):
    """Test memory-specific search index creation."""
    
    def test_create_memory_index(self):
        """Test creating search index from memory files."""
        memory_files = [
            {
                'path': 'memory/2026-02-14.md',
                'content': 'Today I worked on the second brain system. Claude helped with the implementation.',
                'sections': {
                    'decisions_made': ['Use Claude for memory extraction'],
                    'projects': ['second-brain: Memory management system']
                },
                'size': 100,
                'modified': '2026-02-14T10:00:00'
            },
            {
                'path': 'memory/2026-02-15.md', 
                'content': 'Implemented BM25 search for memory retrieval. The search works well.',
                'sections': {
                    'technical_details': ['BM25 algorithm for text search'],
                    'facts': ['BM25 provides good relevance ranking']
                },
                'size': 85,
                'modified': '2026-02-15T09:00:00'
            }
        ]
        
        searcher = create_memory_search_index(memory_files)
        
        # Test that index was created
        stats = searcher.get_stats()
        self.assertEqual(stats['num_documents'], 2)
        
        # Test search functionality
        results = searcher.search("second brain system")
        self.assertGreater(len(results), 0)
        
        # Test that metadata is included
        if results:
            self.assertIn('metadata', results[0])
            self.assertIn('path', results[0]['metadata'])


class TestSearchUtilities(unittest.TestCase):
    """Test search utility functions."""
    
    def test_stop_word_removal(self):
        """Test that stop words are properly removed."""
        searcher = BM25Searcher()
        
        # Test with text containing many stop words
        text = "The quick brown fox is jumping over the lazy dog and cat"
        tokens = searcher.tokenize(text)
        
        # Stop words should be removed
        stop_words = {'the', 'is', 'and'}
        for token in tokens:
            self.assertNotIn(token, stop_words)
        
        # Content words should remain
        content_words = {'quick', 'brown', 'fox', 'jumping', 'lazy', 'dog', 'cat'}
        for word in content_words:
            self.assertIn(word, tokens)
    
    def test_case_insensitive_search(self):
        """Test that search is case insensitive."""
        searcher = BM25Searcher()
        searcher.add_document('doc1', 'Python Programming Language', {})
        
        # Different cases should return same results
        results_lower = searcher.search('python programming')
        results_upper = searcher.search('PYTHON PROGRAMMING')
        results_mixed = searcher.search('Python Programming')
        
        self.assertEqual(len(results_lower), len(results_upper))
        self.assertEqual(len(results_upper), len(results_mixed))
        
        if results_lower:
            # Scores should be identical
            self.assertAlmostEqual(
                results_lower[0]['score'], 
                results_upper[0]['score'], 
                places=4
            )


if __name__ == '__main__':
    unittest.main()