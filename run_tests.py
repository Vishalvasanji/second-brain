#!/usr/bin/env python3
"""
Test runner for Second Brain v2 skill.
"""

import sys
import unittest
import os
from pathlib import Path

def run_tests():
    """Run all tests."""
    # Add project root to Python path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Change to project directory
    os.chdir(project_root)
    
    # Discover and run tests
    loader = unittest.TestLoader()
    test_dir = project_root / 'tests'
    
    if not test_dir.exists():
        print(f"Test directory not found: {test_dir}")
        return False
    
    # Load all tests
    suite = loader.discover(str(test_dir), pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)