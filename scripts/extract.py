#!/usr/bin/env python3
"""Compatibility wrapper for local extractor."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).parent / "extract_v2.py"), run_name="__main__")
