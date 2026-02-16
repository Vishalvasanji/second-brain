#!/usr/bin/env python3
"""
Semantic Memory Search for Second Brain v2

Natural language search over all memory files with ranking and filtering.
"""

import argparse
import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add utils to path
sys.path.append(str(Path(__file__).parent))

from utils.memory_io import (
    load_config, get_memory_files, read_memory_file, 
    load_memory_index, format_memory_snippet
)
from utils.qmd_bridge import create_hybrid_searcher
from utils.scoring import filter_memories_by_score, boost_recent_memories


def parse_date_range(date_range_str: str) -> Tuple[date, date]:
    """Parse date range string like '2026-02-01,2026-02-14'."""
    try:
        start_str, end_str = date_range_str.split(',')
        start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
        return start_date, end_date
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date range format: {e}")


def search_memories(
    query: str,
    config: Dict[str, Any],
    date_range: Optional[Tuple[date, date]] = None,
    limit: int = 10,
    min_score: Optional[float] = None,
    method: str = "auto"
) -> List[Dict[str, Any]]:
    """
    Search memories using hybrid approach.
    
    Args:
        query: Natural language search query
        config: Configuration dict
        date_range: Optional (start_date, end_date) filter
        limit: Maximum results to return
        min_score: Minimum relevance score threshold
        method: Search method ('qmd', 'bm25', 'auto')
    
    Returns:
        List of ranked search results
    """
    # Load memory files
    memory_dir = Path(config['memory_dir']).expanduser()
    memory_files = get_memory_files(memory_dir, date_range)
    
    if not memory_files:
        return []
    
    # Read all memory files
    memory_data = []
    for file_path in memory_files:
        data = read_memory_file(file_path)
        memory_data.append(data)
    
    # Create searcher
    searcher = create_hybrid_searcher(memory_data)
    
    # Perform search
    results = searcher.search(query, limit * 2, method)  # Get extra for filtering
    
    # Load memory scores for ranking boost
    memory_index = load_memory_index(memory_dir)
    
    # Enhance results with additional metadata
    enhanced_results = []
    for result in results:
        file_path = result.get('doc_id') or result.get('path', '')
        
        # Add memory scores if available
        if file_path in memory_index.get('memories', {}):
            memory_info = memory_index['memories'][file_path]
            result['memory_score'] = memory_info.get('score', 1.0)
            result['last_scored'] = memory_info.get('last_scored')
        else:
            result['memory_score'] = 1.0
        
        # Combine search score with memory score
        search_score = result.get('score', 1.0)
        memory_score = result.get('memory_score', 1.0)
        combined_score = (search_score * 0.7) + (memory_score * 0.3)
        result['combined_score'] = combined_score
        
        # Add file metadata
        try:
            file_path_obj = Path(file_path)
            if file_path_obj.exists():
                stat = file_path_obj.stat()
                result['file_size'] = stat.st_size
                result['file_modified'] = datetime.fromtimestamp(stat.st_mtime)
        except Exception:
            pass
        
        enhanced_results.append(result)
    
    # Sort by combined score
    enhanced_results.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
    
    # Apply score filtering
    search_config = config.get('search', {})
    if min_score is None:
        min_score = search_config.get('min_score_threshold', 0.1)
    
    if min_score > 0:
        enhanced_results = [r for r in enhanced_results if r.get('combined_score', 0) >= min_score]
    
    # Apply recent boost if configured
    recent_boost_days = search_config.get('date_boost_recent_days', 0)
    if recent_boost_days > 0:
        cutoff_date = datetime.now() - timedelta(days=recent_boost_days)
        for result in enhanced_results:
            file_modified = result.get('file_modified')
            if file_modified and file_modified > cutoff_date:
                result['combined_score'] *= 1.2
        
        # Re-sort after boost
        enhanced_results.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
    
    return enhanced_results[:limit]


def format_search_results(
    results: List[Dict[str, Any]],
    query: str,
    config: Dict[str, Any],
    format_type: str = "text"
) -> str:
    """Format search results for output."""
    if not results:
        return "No results found."
    
    if format_type == "json":
        return json.dumps(results, indent=2, default=str)
    
    # Text formatting
    output = []
    output.append(f"🔍 Search Results for: \"{query}\"")
    output.append(f"Found {len(results)} result{'s' if len(results) != 1 else ''}")
    output.append("")
    
    search_config = config.get('search', {})
    max_snippet_chars = config.get('output', {}).get('max_snippet_chars', 300)
    context_lines = config.get('output', {}).get('context_lines', 2)
    
    for i, result in enumerate(results, 1):
        file_path = result.get('doc_id') or result.get('path', 'Unknown')
        score = result.get('combined_score', 0)
        file_modified = result.get('file_modified', '')
        
        output.append(f"## {i}. {Path(file_path).name} (score: {score:.2f})")
        
        if file_modified:
            output.append(f"📅 Modified: {file_modified.strftime('%Y-%m-%d %H:%M')}")
        
        # Show highlights or content snippet
        highlights = result.get('highlights', [])
        if highlights:
            output.append("🔗 Matches:")
            for highlight in highlights[:3]:  # Show top 3 highlights
                # Clean up highlight
                clean_highlight = highlight.strip()
                if len(clean_highlight) > max_snippet_chars:
                    clean_highlight = clean_highlight[:max_snippet_chars-3] + "..."
                output.append(f"  • {clean_highlight}")
        else:
            # Show content snippet
            content = result.get('content', '')
            if content:
                snippet = format_memory_snippet(
                    content, query, max_snippet_chars, context_lines
                )
                output.append(f"📄 Content:")
                output.append(f"  {snippet}")
        
        output.append("")
    
    return "\n".join(output)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Search memory files using natural language queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 search.py "decisions about model choice"
  python3 search.py --date-range "2026-02-01,2026-02-14" "Discord features"
  python3 search.py --limit 5 --format json "DPU debugging"
  python3 search.py --method bm25 "recent action items"
        """
    )
    
    parser.add_argument('query', help='Natural language search query')
    
    parser.add_argument(
        '--config', 
        type=Path,
        help='Path to configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--date-range',
        type=parse_date_range,
        help='Date range filter (format: YYYY-MM-DD,YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of results (default: 10)'
    )
    
    parser.add_argument(
        '--min-score',
        type=float,
        help='Minimum relevance score threshold'
    )
    
    parser.add_argument(
        '--method',
        choices=['qmd', 'bm25', 'auto'],
        default='auto',
        help='Search method (default: auto)'
    )
    
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show debug information'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        if args.verbose:
            print(f"Using config: {args.config or 'config.yaml'}")
            print(f"Memory directory: {config['memory_dir']}")
            if args.date_range:
                print(f"Date range: {args.date_range[0]} to {args.date_range[1]}")
        
        # Perform search
        results = search_memories(
            query=args.query,
            config=config,
            date_range=args.date_range,
            limit=args.limit,
            min_score=args.min_score,
            method=args.method
        )
        
        # Format and output results
        output = format_search_results(results, args.query, config, args.format)
        print(output)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()