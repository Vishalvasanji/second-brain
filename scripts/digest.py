#!/usr/bin/env python3
"""Simple local digest command."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).parent / "weekly.py"), run_name="__main__")
