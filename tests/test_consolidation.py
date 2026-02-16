#!/usr/bin/env python3
"""
Unit tests for memory consolidation functionality.
"""

import unittest
from pathlib import Path
import sys
import tempfile
from datetime import datetime

# Add utils to path  
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

import consolidate


class TestConsolidationUtilities(unittest.TestCase):
    """Test consolidation utility functions."""
    
    def test_parse_consolidation_output(self):
        """Test parsing AI consolidation output."""
        ai_output = """## Facts & Preferences
- User prefers Claude for AI assistance
- Uses Python for development

## Decisions Made
- Decided to use BM25 for search fallback
- Will implement nightly pipeline

## Key People
- **Alice**: AI researcher working on memory systems
- **Bob**: Developer on the OpenClaw team

## Action Items
- [ ] Set up daily extraction
- [x] Implement search functionality
"""
        
        sections = consolidate.parse_consolidation_output(ai_output)
        
        # Check that sections are parsed correctly
        self.assertIn('facts_&_preferences', sections)
        self.assertIn('decisions_made', sections)
        self.assertIn('key_people', sections)
        self.assertIn('action_items', sections)
        
        # Check content
        facts = sections['facts_&_preferences']
        self.assertEqual(len(facts), 2)
        self.assertIn('User prefers Claude for AI assistance', facts)
        
        people = sections['key_people']
        self.assertEqual(len(people), 2)
        self.assertIn('**Alice**: AI researcher working on memory systems', people)
    
    def test_duplicate_detection(self):
        """Test duplicate memory detection."""
        existing_memory = "User prefers Python for development and uses Claude for AI assistance."
        
        # Similar items should be detected as duplicates
        similar_item = "User likes Python programming and Claude AI"
        duplicate = consolidate.detect_duplicates(existing_memory, similar_item, threshold=0.6)
        self.assertTrue(duplicate)
        
        # Different items should not be duplicates
        different_item = "The weather is sunny today"
        not_duplicate = consolidate.detect_duplicates(existing_memory, different_item, threshold=0.6)
        self.assertFalse(not_duplicate)
    
    def test_memory_section_merging(self):
        """Test merging memory sections."""
        existing_sections = {
            'facts_&_preferences': [
                'User prefers Python',
                'Uses VSCode editor'
            ],
            'decisions_made': [
                'Decided to use Claude API'
            ]
        }
        
        new_sections = {
            'facts_&_preferences': [
                'User likes TypeScript too',  # New fact
                'User prefers Python'        # Duplicate (should be filtered)
            ],
            'decisions_made': [
                'Will implement BM25 search'  # New decision
            ],
            'technical_details': [
                'BM25 algorithm for search'   # New section
            ]
        }
        
        merged = consolidate.merge_memory_sections(existing_sections, new_sections)
        
        # Check that new non-duplicate items are added
        facts = merged['facts_&_preferences']
        self.assertIn('User likes TypeScript too', facts)
        self.assertIn('User prefers Python', facts)  # Original should remain
        self.assertEqual(len([f for f in facts if 'Python' in f]), 1)  # No duplicates
        
        # Check new sections are added
        self.assertIn('technical_details', merged)
        self.assertIn('BM25 algorithm for search', merged['technical_details'])
    
    def test_memory_md_formatting(self):
        """Test MEMORY.md formatting."""
        sections = {
            'facts_&_preferences': [
                'User prefers Python',
                'Uses Claude for AI tasks'
            ],
            'decisions_made': [
                'Decided to implement second brain system'
            ],
            'key_people': [
                '**Alice**: AI researcher'
            ]
        }
        
        metadata = {
            'last_consolidated': '2026-02-15T10:00:00'
        }
        
        formatted = consolidate.format_memory_md(sections, metadata)
        
        # Check structure
        self.assertIn('# MEMORY.md - Long-Term Memory', formatted)
        self.assertIn('*Last consolidated: 2026-02-15 10:00:00*', formatted)
        self.assertIn('## Facts & Preferences', formatted)
        self.assertIn('## Decisions Made', formatted)
        self.assertIn('## Key People', formatted)
        
        # Check content
        self.assertIn('- User prefers Python', formatted)
        self.assertIn('- **Alice**: AI researcher', formatted)


class TestMemoryCollection(unittest.TestCase):
    """Test memory collection and formatting."""
    
    def setUp(self):
        """Set up temporary memory files for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = Path(self.temp_dir) / "memory"
        self.memory_dir.mkdir()
        
        # Create sample memory files
        self.create_sample_memory_file("2026-02-14.md", """
## Facts & Preferences
- User prefers Python for development
- Uses Claude for AI assistance

## Decisions Made
- Decided to build second brain system
- Will use BM25 for search fallback

## Action Items
- [ ] Implement daily extraction
- [x] Create search functionality
""")
        
        self.create_sample_memory_file("2026-02-15.md", """
## Technical Details
- Implemented BM25 algorithm
- Added entity graph functionality

## Key People
- **Alice**: Helped with system design
- **Bob**: Tested the search features
""")
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_sample_memory_file(self, filename: str, content: str):
        """Create a sample memory file."""
        file_path = self.memory_dir / filename
        with open(file_path, 'w') as f:
            f.write(content.strip())
    
    def test_collect_recent_memories(self):
        """Test collecting recent memory files."""
        memories = consolidate.collect_recent_memories(self.memory_dir, days_back=7)
        
        # Should find both test files
        self.assertEqual(len(memories), 2)
        
        # Check that content is loaded
        for memory in memories:
            self.assertIn('path', memory)
            self.assertIn('content', memory)
            self.assertIn('sections', memory)
    
    def test_format_memories_for_consolidation(self):
        """Test formatting memories for AI consolidation."""
        memories = consolidate.collect_recent_memories(self.memory_dir, days_back=7)
        formatted = consolidate.format_memories_for_consolidation(memories)
        
        # Should contain file headers and sections
        self.assertIn('### 2026-02-14.md', formatted)
        self.assertIn('### 2026-02-15.md', formatted)
        self.assertIn('**Decisions Made:**', formatted)
        self.assertIn('**Technical Details:**', formatted)
        
        # Should contain actual content
        self.assertIn('User prefers Python', formatted)
        self.assertIn('BM25 algorithm', formatted)


class TestExistingMemoryHandling(unittest.TestCase):
    """Test handling of existing MEMORY.md files."""
    
    def setUp(self):
        """Set up temporary directory with MEMORY.md."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_md_path = Path(self.temp_dir) / "MEMORY.md"
        
        # Create existing MEMORY.md
        existing_content = """# MEMORY.md - Long-Term Memory

*Last consolidated: 2026-02-10 09:00:00*

## Facts & Preferences
- User prefers Python for development
- Uses VSCode as primary editor

## Decisions Made
- Decided to use Claude API for extraction
"""
        
        with open(self.memory_md_path, 'w') as f:
            f.write(existing_content)
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_load_existing_memory(self):
        """Test loading existing MEMORY.md file."""
        existing = consolidate.load_existing_memory(self.memory_md_path)
        
        # Check structure
        self.assertIn('content', existing)
        self.assertIn('sections', existing)
        self.assertIn('last_modified', existing)
        
        # Check parsed sections
        sections = existing['sections']
        self.assertIn('facts_&_preferences', sections)
        self.assertIn('decisions_made', sections)
        
        facts = sections['facts_&_preferences']
        self.assertIn('User prefers Python for development', facts)
    
    def test_load_nonexistent_memory(self):
        """Test loading non-existent MEMORY.md file."""
        nonexistent_path = Path(self.temp_dir) / "nonexistent.md"
        existing = consolidate.load_existing_memory(nonexistent_path)
        
        # Should return empty structure
        self.assertEqual(existing['content'], '')
        self.assertEqual(existing['sections'], {})
        self.assertIsNone(existing['last_modified'])


if __name__ == '__main__':
    unittest.main()