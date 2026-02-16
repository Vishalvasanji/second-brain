#!/usr/bin/env python3
"""
Session Archiver for Second Brain System

Archives full session files to compressed storage before compaction happens.
Provides status reporting and search capabilities for archived sessions.
"""

import argparse
import gzip
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Iterator, Optional, Tuple, List, Dict


# Constants
SESSIONS_DIR = Path.home() / ".openclaw/agents/main/sessions"
ARCHIVE_DIR = Path.home() / ".openclaw/agents/main/sessions-archive"
COMPACTION_THRESHOLD_KB = 500
DATE_FORMAT = "%Y-%m-%d"


class SessionArchiver:
    """Manages archiving, status reporting, and searching of session files."""

    def __init__(self):
        self.sessions_dir = SESSIONS_DIR
        self.archive_dir = ARCHIVE_DIR
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def get_session_files(self, modified_date: Optional[date] = None,
                         session_id: Optional[str] = None) -> List[Path]:
        """Get session files matching the criteria.

        Args:
            modified_date: Filter by modification date (default: None for all)
            session_id: Specific session ID to retrieve (default: None)

        Returns:
            List of matching session file paths
        """
        if not self.sessions_dir.exists():
            return []

        session_files = []

        for filepath in self.sessions_dir.glob("*.jsonl"):
            # Filter by session ID if specified
            if session_id and filepath.stem != session_id:
                continue

            # Filter by modification date if specified
            if modified_date:
                mtime = datetime.fromtimestamp(filepath.stat().st_mtime).date()
                if mtime != modified_date:
                    continue

            session_files.append(filepath)

        return sorted(session_files)

    def parse_session_header(self, filepath: Path) -> Tuple[str, datetime]:
        """Parse the first line of a session file to extract ID and timestamp.

        Args:
            filepath: Path to the session file

        Returns:
            Tuple of (session_id, timestamp)

        Raises:
            ValueError: If header cannot be parsed
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()

            if not first_line:
                raise ValueError("Empty session file")

            header = json.loads(first_line)

            # Try to get session ID and timestamp from various possible locations
            session_id = header.get('session_id') or header.get('id') or filepath.stem

            # Try multiple timestamp fields
            timestamp_str = (header.get('timestamp') or
                           header.get('created_at') or
                           header.get('ts'))

            if timestamp_str:
                # Parse ISO format timestamp
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Fallback to file modification time
                timestamp = datetime.fromtimestamp(filepath.stat().st_mtime)

            return session_id, timestamp

        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"Failed to parse session header: {e}")

    def archive_session(self, filepath: Path) -> Dict[str, any]:
        """Archive a single session file.

        Args:
            filepath: Path to the session file to archive

        Returns:
            Dictionary with archive statistics
        """
        try:
            session_id, timestamp = self.parse_session_header(filepath)
        except ValueError as e:
            return {
                'success': False,
                'session_id': filepath.stem,
                'error': str(e)
            }

        # Create date-based subdirectory
        session_date = timestamp.strftime(DATE_FORMAT)
        date_dir = self.archive_dir / session_date
        date_dir.mkdir(parents=True, exist_ok=True)

        # Archive file path
        archive_path = date_dir / f"{session_id}.jsonl.gz"

        # Read original file and compress
        try:
            with open(filepath, 'rb') as f_in:
                original_data = f_in.read()
                original_size = len(original_data)

            with gzip.open(archive_path, 'wb', compresslevel=9) as f_out:
                f_out.write(original_data)

            compressed_size = archive_path.stat().st_size
            compression_ratio = (1 - compressed_size / original_size) * 100

            return {
                'success': True,
                'session_id': session_id,
                'date': session_date,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'archive_path': archive_path
            }

        except OSError as e:
            return {
                'success': False,
                'session_id': session_id,
                'error': f"I/O error: {e}"
            }

    def archive_sessions(self, modified_date: Optional[date] = None,
                        all_sessions: bool = False,
                        session_id: Optional[str] = None) -> List[Dict]:
        """Archive multiple sessions based on criteria.

        Args:
            modified_date: Archive sessions modified on this date
            all_sessions: Archive all sessions
            session_id: Archive specific session

        Returns:
            List of archive result dictionaries
        """
        # Determine which sessions to archive
        if all_sessions:
            session_files = self.get_session_files()
        elif session_id:
            session_files = self.get_session_files(session_id=session_id)
        else:
            # Default: today's modified sessions
            target_date = modified_date or date.today()
            session_files = self.get_session_files(modified_date=target_date)

        if not session_files:
            return []

        results = []
        for filepath in session_files:
            result = self.archive_session(filepath)
            results.append(result)

            # Print progress
            if result['success']:
                print(f"Archived: {result['session_id']} ({result['date']})")
                print(f"  Original: {result['original_size']:,} bytes")
                print(f"  Compressed: {result['compressed_size']:,} bytes")
                print(f"  Ratio: {result['compression_ratio']:.1f}% reduction")
            else:
                print(f"Failed: {result['session_id']} - {result['error']}",
                      file=sys.stderr)

        return results

    def get_archive_status(self) -> Dict:
        """Get comprehensive archive and session status.

        Returns:
            Dictionary with status information
        """
        status = {
            'archived_sessions': [],
            'active_sessions': [],
            'total_archived_original_size': 0,
            'total_archived_compressed_size': 0,
            'total_active_size': 0,
            'large_sessions': []
        }

        # Scan archived sessions
        if self.archive_dir.exists():
            for date_dir in sorted(self.archive_dir.iterdir()):
                if not date_dir.is_dir():
                    continue

                for archive_file in sorted(date_dir.glob("*.jsonl.gz")):
                    compressed_size = archive_file.stat().st_size

                    # Estimate original size by decompressing
                    try:
                        with gzip.open(archive_file, 'rb') as f:
                            original_size = len(f.read())
                    except Exception:
                        original_size = compressed_size * 3  # Rough estimate

                    status['archived_sessions'].append({
                        'session_id': archive_file.stem,
                        'date': date_dir.name,
                        'original_size': original_size,
                        'compressed_size': compressed_size
                    })

                    status['total_archived_original_size'] += original_size
                    status['total_archived_compressed_size'] += compressed_size

        # Scan active sessions
        if self.sessions_dir.exists():
            for session_file in self.sessions_dir.glob("*.jsonl"):
                size = session_file.stat().st_size

                status['active_sessions'].append({
                    'session_id': session_file.stem,
                    'size': size
                })

                status['total_active_size'] += size

                # Check for sessions approaching compaction threshold
                size_kb = size / 1024
                if size_kb >= COMPACTION_THRESHOLD_KB:
                    status['large_sessions'].append({
                        'session_id': session_file.stem,
                        'size_kb': size_kb
                    })

        return status

    def print_status(self):
        """Print formatted status report."""
        status = self.get_archive_status()

        print("=" * 70)
        print("SESSION ARCHIVE STATUS")
        print("=" * 70)

        # Archived sessions
        print(f"\nArchived Sessions: {len(status['archived_sessions'])}")
        if status['archived_sessions']:
            print(f"  Total Original Size: {status['total_archived_original_size']:,} bytes "
                  f"({status['total_archived_original_size'] / 1024 / 1024:.2f} MB)")
            print(f"  Total Compressed Size: {status['total_archived_compressed_size']:,} bytes "
                  f"({status['total_archived_compressed_size'] / 1024 / 1024:.2f} MB)")

            if status['total_archived_original_size'] > 0:
                overall_ratio = (1 - status['total_archived_compressed_size'] /
                               status['total_archived_original_size']) * 100
                print(f"  Overall Compression: {overall_ratio:.1f}% reduction")

            # Group by date
            by_date = {}
            for session in status['archived_sessions']:
                date_key = session['date']
                if date_key not in by_date:
                    by_date[date_key] = []
                by_date[date_key].append(session)

            print("\n  By Date:")
            for date_key in sorted(by_date.keys(), reverse=True):
                sessions = by_date[date_key]
                total_orig = sum(s['original_size'] for s in sessions)
                total_comp = sum(s['compressed_size'] for s in sessions)
                print(f"    {date_key}: {len(sessions)} sessions "
                      f"({total_orig:,} -> {total_comp:,} bytes)")

        # Active sessions
        print(f"\nActive Sessions: {len(status['active_sessions'])}")
        if status['active_sessions']:
            print(f"  Total Size: {status['total_active_size']:,} bytes "
                  f"({status['total_active_size'] / 1024 / 1024:.2f} MB)")

            # Show top 10 by size
            top_sessions = sorted(status['active_sessions'],
                                 key=lambda x: x['size'], reverse=True)[:10]
            print("\n  Largest Sessions:")
            for session in top_sessions:
                size_kb = session['size'] / 1024
                print(f"    {session['session_id']}: {size_kb:.1f} KB")

        # Warnings
        if status['large_sessions']:
            print("\n" + "!" * 70)
            print("WARNING: Sessions Approaching Compaction Threshold")
            print("!" * 70)
            for session in status['large_sessions']:
                print(f"  {session['session_id']}: {session['size_kb']:.1f} KB "
                      f"(threshold: {COMPACTION_THRESHOLD_KB} KB)")
            print("\nConsider archiving these sessions before they are compacted.")

        print("=" * 70)

    def search_archived_sessions(self, keyword: str) -> Iterator[Tuple[str, str, str, int]]:
        """Search through archived sessions for a keyword.

        Args:
            keyword: Keyword to search for (case-insensitive)

        Yields:
            Tuples of (session_id, date, matching_line, line_number)
        """
        keyword_lower = keyword.lower()

        if not self.archive_dir.exists():
            return

        for date_dir in sorted(self.archive_dir.iterdir()):
            if not date_dir.is_dir():
                continue

            for archive_file in sorted(date_dir.glob("*.jsonl.gz")):
                session_id = archive_file.stem
                session_date = date_dir.name

                try:
                    with gzip.open(archive_file, 'rt', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            try:
                                entry = json.loads(line.strip())

                                # Only search message entries
                                if entry.get('type') != 'message':
                                    continue

                                # Extract text content
                                text_content = self._extract_text_from_entry(entry)

                                # Search for keyword
                                if keyword_lower in text_content.lower():
                                    yield (session_id, session_date, line.strip(), line_num)

                            except json.JSONDecodeError:
                                continue

                except Exception as e:
                    print(f"Error reading {archive_file}: {e}", file=sys.stderr)

    def _extract_text_from_entry(self, entry: Dict) -> str:
        """Extract searchable text from a session entry.

        Args:
            entry: JSON entry from session file (type=message)

        Returns:
            Concatenated text content
        """
        text_parts = []

        # Messages are nested: entry['message']['content']
        message = entry.get('message', entry)
        content = message.get('content', '')

        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                    elif 'text' in block:
                        text_parts.append(block['text'])
                elif isinstance(block, str):
                    text_parts.append(block)

        return ' '.join(text_parts)

    def print_search_results(self, keyword: str, max_line_length: int = 150):
        """Print search results for a keyword.

        Args:
            keyword: Keyword to search for
            max_line_length: Maximum length of displayed lines
        """
        print(f"Searching archived sessions for: '{keyword}'")
        print("=" * 70)

        results_count = 0
        current_session = None

        for session_id, session_date, line, line_num in self.search_archived_sessions(keyword):
            if session_id != current_session:
                if current_session is not None:
                    print()
                print(f"\nSession: {session_id} ({session_date})")
                print("-" * 70)
                current_session = session_id

            # Truncate long lines
            if len(line) > max_line_length:
                display_line = line[:max_line_length] + "..."
            else:
                display_line = line

            print(f"  Line {line_num}: {display_line}")
            results_count += 1

        print("\n" + "=" * 70)
        print(f"Found {results_count} matches")


def main():
    """Main entry point for the archive CLI."""
    parser = argparse.ArgumentParser(
        description="Session archiver for second brain system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Archive all sessions modified today
  %(prog)s archive

  # Archive all sessions modified on a specific date
  %(prog)s archive --date 2026-02-10

  # Archive all sessions
  %(prog)s archive --all

  # Archive a specific session
  %(prog)s archive --session abc123

  # Show archive status
  %(prog)s status

  # Search archived sessions
  %(prog)s search "error message"
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Archive command
    archive_parser = subparsers.add_parser(
        'archive',
        help='Archive session files'
    )
    archive_parser.add_argument(
        '--date',
        type=str,
        help=f'Archive sessions modified on this date (format: {DATE_FORMAT})'
    )
    archive_parser.add_argument(
        '--all',
        action='store_true',
        help='Archive all sessions'
    )
    archive_parser.add_argument(
        '--session',
        type=str,
        help='Archive a specific session by ID'
    )

    # Status command
    subparsers.add_parser(
        'status',
        help='Show archive status and size report'
    )

    # Search command
    search_parser = subparsers.add_parser(
        'search',
        help='Search archived sessions for a keyword'
    )
    search_parser.add_argument(
        'keyword',
        type=str,
        help='Keyword to search for'
    )

    # Parse arguments
    args = parser.parse_args()

    # Default to archive command if none specified
    if not args.command:
        args.command = 'archive'
        args.date = None
        args.all = False
        args.session = None

    # Create archiver instance
    archiver = SessionArchiver()

    # Execute command
    try:
        if args.command == 'archive':
            # Parse date if provided
            target_date = None
            if args.date:
                try:
                    target_date = datetime.strptime(args.date, DATE_FORMAT).date()
                except ValueError:
                    print(f"Error: Invalid date format. Use {DATE_FORMAT}",
                          file=sys.stderr)
                    return 1

            results = archiver.archive_sessions(
                modified_date=target_date,
                all_sessions=args.all,
                session_id=args.session
            )

            if not results:
                print("No sessions found to archive.")
            else:
                success_count = sum(1 for r in results if r['success'])
                print(f"\nArchived {success_count}/{len(results)} sessions successfully.")

        elif args.command == 'status':
            archiver.print_status()

        elif args.command == 'search':
            archiver.print_search_results(args.keyword)

        return 0

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
