#!/usr/bin/env python3
"""
Memory I/O utilities for Second Brain v2

Handles reading/writing memory files, API key management, and file operations.
"""

import json
import os
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import shutil


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Expand paths
    for key, value in config.items():
        if key.endswith('_dir') or key.endswith('_md'):
            if isinstance(value, str) and value.startswith('~'):
                config[key] = str(Path(value).expanduser())
    
    return config


def get_api_key() -> str:
    """Get Anthropic API key from environment or auth profiles."""
    # Try environment variable first
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return api_key

    # Try auth profiles
    auth_profiles_path = Path.home() / ".openclaw/agents/main/agent/auth-profiles.json"
    try:
        if auth_profiles_path.exists():
            with open(auth_profiles_path, 'r') as f:
                data = json.load(f)
                profiles = data.get("profiles", data)
                if "anthropic:default" in profiles:
                    token = profiles["anthropic:default"].get("token")
                    if token:
                        return token
    except Exception as e:
        print(f"Warning: Could not read auth profiles: {e}")

    raise ValueError("No API key found. Set ANTHROPIC_API_KEY or configure auth profile.")


def get_memory_files(memory_dir: Path, date_range: Optional[Tuple[date, date]] = None) -> List[Path]:
    """Get all memory files, optionally filtered by date range."""
    memory_dir = Path(memory_dir)
    if not memory_dir.exists():
        return []
    
    files = []
    for file_path in memory_dir.glob("*.md"):
        # Skip files that start with . (indexes, etc.)
        if file_path.name.startswith('.'):
            continue
            
        # Try to parse date from filename (YYYY-MM-DD.md format)
        try:
            file_date = datetime.strptime(file_path.stem, "%Y-%m-%d").date()
            if date_range is None or (date_range[0] <= file_date <= date_range[1]):
                files.append(file_path)
        except ValueError:
            # Not a date-formatted file, include it anyway
            files.append(file_path)
    
    return sorted(files)


def read_memory_file(file_path: Path) -> Dict[str, Any]:
    """Read a memory file and return structured data."""
    if not file_path.exists():
        return {"path": str(file_path), "content": "", "sections": {}}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse sections if it's a structured memory file
    sections = parse_memory_sections(content)
    
    # Get file metadata
    stat = file_path.stat()
    
    return {
        "path": str(file_path),
        "content": content,
        "sections": sections,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime),
        "created": datetime.fromtimestamp(stat.st_ctime)
    }


def parse_memory_sections(content: str) -> Dict[str, List[str]]:
    """Parse memory file into structured sections."""
    sections = {}
    current_section = None
    current_items = []
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Check for section headers (## Section Name)
        if line.startswith('## '):
            if current_section:
                sections[current_section] = current_items
            current_section = line[3:].strip().lower().replace(' ', '_')
            current_items = []
        elif line.startswith('- ') and current_section:
            # Remove the leading "- " and add to current section
            item = line[2:].strip()
            if item and item != "None":
                current_items.append(item)
    
    # Don't forget the last section
    if current_section:
        sections[current_section] = current_items
    
    return sections


def write_memory_file(file_path: Path, content: str, backup: bool = True) -> None:
    """Write content to memory file with optional backup."""
    file_path = Path(file_path)
    
    # Create backup if file exists
    if backup and file_path.exists():
        backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
        shutil.copy2(file_path, backup_path)
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def load_memory_index(memory_dir: Path) -> Dict[str, Any]:
    """Load the memory scoring index."""
    index_path = Path(memory_dir) / ".memory-index.json"
    if not index_path.exists():
        return {"memories": {}, "last_updated": None, "version": "1.0"}
    
    try:
        with open(index_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"memories": {}, "last_updated": None, "version": "1.0"}


def save_memory_index(memory_dir: Path, index: Dict[str, Any]) -> None:
    """Save the memory scoring index."""
    index_path = Path(memory_dir) / ".memory-index.json"
    index["last_updated"] = datetime.now().isoformat()
    
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)


def load_pipeline_log(memory_dir: Path) -> List[Dict[str, Any]]:
    """Load pipeline execution log."""
    log_path = Path(memory_dir) / ".pipeline-log.json"
    if not log_path.exists():
        return []
    
    try:
        with open(log_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_pipeline_log(memory_dir: Path, log_entries: List[Dict[str, Any]]) -> None:
    """Save pipeline execution log."""
    log_path = Path(memory_dir) / ".pipeline-log.json"
    
    with open(log_path, 'w') as f:
        json.dump(log_entries, f, indent=2)


def append_pipeline_log(memory_dir: Path, entry: Dict[str, Any]) -> None:
    """Append entry to pipeline log."""
    log = load_pipeline_log(memory_dir)
    entry["timestamp"] = datetime.now().isoformat()
    log.append(entry)
    
    # Keep only last 100 entries
    if len(log) > 100:
        log = log[-100:]
    
    save_pipeline_log(memory_dir, log)


def find_session_files(session_dir: Path, target_date: Optional[date] = None) -> List[Path]:
    """Find session JSONL files, optionally filtered by modification date."""
    session_dir = Path(session_dir)
    if not session_dir.exists():
        return []
    
    session_files = []
    for file_path in session_dir.glob("*.jsonl"):
        if target_date:
            # Check if file was modified on target date
            mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mod_time.date() == target_date:
                session_files.append(file_path)
        else:
            session_files.append(file_path)
    
    return sorted(session_files, key=lambda p: p.stat().st_mtime, reverse=True)


def extract_text_content(content: Any) -> str:
    """Extract text from message content (handles both string and list formats)."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)

    return str(content)


def format_memory_snippet(content: str, query: str = "", max_chars: int = 300, context_lines: int = 2) -> str:
    """Format a memory snippet with optional highlighting."""
    lines = content.split('\n')
    
    if query:
        # Find lines containing the query (case insensitive)
        query_lower = query.lower()
        matching_lines = []
        
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # Include context lines
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                matching_lines.extend(range(start, end))
        
        # Remove duplicates and sort
        matching_lines = sorted(set(matching_lines))
        
        if matching_lines:
            snippet_lines = [lines[i] for i in matching_lines]
            snippet = '\n'.join(snippet_lines)
        else:
            # No matches, return beginning
            snippet = '\n'.join(lines[:10])
    else:
        # No query, return beginning
        snippet = '\n'.join(lines[:10])
    
    # Truncate if too long
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars-3] + "..."
    
    return snippet


def ensure_memory_dir(memory_dir: Path) -> None:
    """Ensure memory directory exists."""
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)