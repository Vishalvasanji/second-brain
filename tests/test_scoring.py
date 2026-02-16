#!/usr/bin/env python3
"""
Unit tests for memory scoring algorithms.
"""

import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

from utils.scoring import (
    calculate_memory_score, parse_memory_timestamp, 
    calculate_frequency_scores, normalize_text_for_grouping
)


class TestMemoryScoring(unittest.TestCase):
    """Test memory scoring algorithms."""
    
    def setUp(self):
        """Set up test configuration."""
        self.config = {
            'scoring': {
                'decay_half_life_days': 14,
                'category_weights': {
                    'decisions': 1.5,
                    'preferences': 1.3,
                    'facts': 1.0,
                    'action_items': 1.2,
                    'transient': 0.5
                },
                'frequency_boost': 1.2,
                'max_score': 5.0
            }
        }
        
        self.reference_date = datetime(2026, 2, 15)
    
    def test_basic_scoring(self):
        """Test basic memory scoring."""
        memory = {
            'text': 'Test memory',
            'category': 'facts',
            'timestamp': self.reference_date,
            'frequency': 1
        }
        
        score = calculate_memory_score(memory, self.config, self.reference_date)
        
        # Should be base score (1.0) * category weight (1.0) * no decay = 1.0
        self.assertAlmostEqual(score, 1.0, places=2)
    
    def test_category_weights(self):
        """Test category weight application."""
        memories = [
            {'text': 'Decision', 'category': 'decisions', 'timestamp': self.reference_date, 'frequency': 1},
            {'text': 'Fact', 'category': 'facts', 'timestamp': self.reference_date, 'frequency': 1},
            {'text': 'Transient', 'category': 'transient', 'timestamp': self.reference_date, 'frequency': 1}
        ]
        
        scores = [calculate_memory_score(m, self.config, self.reference_date) for m in memories]
        
        # Decisions should have highest score, transient lowest
        self.assertGreater(scores[0], scores[1])  # decisions > facts
        self.assertGreater(scores[1], scores[2])  # facts > transient
        self.assertAlmostEqual(scores[0], 1.5, places=2)  # decisions weight
        self.assertAlmostEqual(scores[2], 0.5, places=2)  # transient weight
    
    def test_time_decay(self):
        """Test time-based score decay."""
        # Recent memory
        recent_memory = {
            'text': 'Recent memory',
            'category': 'facts',
            'timestamp': self.reference_date,
            'frequency': 1
        }
        
        # Old memory (28 days = 2 half-lives)
        old_memory = {
            'text': 'Old memory',
            'category': 'facts',
            'timestamp': self.reference_date - timedelta(days=28),
            'frequency': 1
        }
        
        recent_score = calculate_memory_score(recent_memory, self.config, self.reference_date)
        old_score = calculate_memory_score(old_memory, self.config, self.reference_date)
        
        # Old score should be roughly 1/4 of recent (2 half-lives)
        self.assertGreater(recent_score, old_score)
        self.assertAlmostEqual(old_score, recent_score * 0.25, places=2)
    
    def test_frequency_boost(self):
        """Test frequency boost application."""
        single_memory = {
            'text': 'Single mention',
            'category': 'facts',
            'timestamp': self.reference_date,
            'frequency': 1
        }
        
        frequent_memory = {
            'text': 'Frequent mention',
            'category': 'facts',
            'timestamp': self.reference_date,
            'frequency': 3
        }
        
        single_score = calculate_memory_score(single_memory, self.config, self.reference_date)
        frequent_score = calculate_memory_score(frequent_memory, self.config, self.reference_date)
        
        # Frequent memory should have higher score
        self.assertGreater(frequent_score, single_score)
    
    def test_completed_action_penalty(self):
        """Test penalty for completed action items."""
        pending_action = {
            'text': '[ ] Do something important',
            'category': 'action_items',
            'timestamp': self.reference_date,
            'frequency': 1
        }
        
        completed_action = {
            'text': '[x] Completed task',
            'category': 'action_items',
            'timestamp': self.reference_date,
            'frequency': 1
        }
        
        pending_score = calculate_memory_score(pending_action, self.config, self.reference_date)
        completed_score = calculate_memory_score(completed_action, self.config, self.reference_date)
        
        # Completed action should have lower score
        self.assertLess(completed_score, pending_score)
    
    def test_max_score_cap(self):
        """Test that scores are capped at max_score."""
        high_frequency_memory = {
            'text': 'Very important decision mentioned many times',
            'category': 'decisions',
            'timestamp': self.reference_date,
            'frequency': 100,  # Very high frequency
            'entities': ['person1', 'person2', 'person3', 'person4']  # Many entities
        }
        
        score = calculate_memory_score(high_frequency_memory, self.config, self.reference_date)
        max_score = self.config['scoring']['max_score']
        
        # Score should not exceed max_score
        self.assertLessEqual(score, max_score)


class TestTimestampParsing(unittest.TestCase):
    """Test timestamp parsing utilities."""
    
    def test_parse_datetime_object(self):
        """Test parsing datetime objects."""
        dt = datetime(2026, 2, 15, 10, 30, 0)
        result = parse_memory_timestamp(dt)
        self.assertEqual(result, dt)
    
    def test_parse_iso_string(self):
        """Test parsing ISO format strings."""
        iso_string = "2026-02-15T10:30:00"
        result = parse_memory_timestamp(iso_string)
        expected = datetime(2026, 2, 15, 10, 30, 0)
        self.assertEqual(result, expected)
    
    def test_parse_date_string(self):
        """Test parsing date-only strings."""
        date_string = "2026-02-15"
        result = parse_memory_timestamp(date_string)
        expected = datetime(2026, 2, 15, 0, 0, 0)
        self.assertEqual(result, expected)
    
    def test_parse_invalid_string(self):
        """Test parsing invalid strings."""
        invalid_string = "not a date"
        result = parse_memory_timestamp(invalid_string)
        self.assertIsNone(result)


class TestFrequencyScoring(unittest.TestCase):
    """Test frequency scoring algorithms."""
    
    def test_basic_frequency_calculation(self):
        """Test basic frequency calculation."""
        memories = [
            {'text': 'This is about project Alpha', 'id': 'mem1'},
            {'text': 'This is about project Alpha too', 'id': 'mem2'},
            {'text': 'Different topic entirely', 'id': 'mem3'}
        ]
        
        frequencies = calculate_frequency_scores(memories)
        
        # Alpha-related memories should have frequency > 1
        # Different topic should have frequency = 1
        self.assertEqual(len(frequencies), 3)
        self.assertGreaterEqual(min(frequencies.values()), 1)
    
    def test_text_normalization(self):
        """Test text normalization for grouping."""
        test_cases = [
            ("- [ ] Complete the project setup", "complete the project setup"),
            ("- [x] Finished the documentation", "finished the documentation"),
            ("- Some regular text here", "some regular text here"),
            ("A very long piece of text that should definitely be truncated beyond the fifty character limit here", "a very long piece of text that should definitely b")
        ]
        
        for input_text, expected in test_cases:
            result = normalize_text_for_grouping(input_text)
            self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()