#!/usr/bin/env python3
"""
Memory Scoring & Decay for Second Brain v2

Assign relevance scores to memories with configurable decay algorithms.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add utils to path
sys.path.append(str(Path(__file__).parent))

from utils.memory_io import (
    load_config, get_memory_files, read_memory_file,
    load_memory_index, save_memory_index
)
from utils.scoring import (
    calculate_memory_score, calculate_frequency_scores,
    calculate_category_distribution, calculate_entity_scores,
    parse_memory_timestamp
)


def extract_memories_from_file(file_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract individual memories from a memory file."""
    memories = []
    sections = file_data.get('sections', {})
    file_path = file_data.get('path', '')
    file_modified = file_data.get('modified', datetime.now())
    
    # Extract memories from each section
    for section_name, items in sections.items():
        category = section_name.replace('_', ' ')
        
        for i, item in enumerate(items):
            memory = {
                'id': f"{Path(file_path).stem}_{section_name}_{i}",
                'text': item,
                'category': category,
                'source_file': file_path,
                'timestamp': file_modified,
                'section': section_name
            }
            
            # Try to extract entities from the text
            if section_name == 'people_mentioned':
                # Extract person name from "**Name**: context" format
                if item.startswith('**') and '**:' in item:
                    name = item.split('**:')[0].strip('*')
                    memory['entities'] = [name]
                    memory['entity_type'] = 'person'
            
            memories.append(memory)
    
    return memories


def score_all_memories(
    config: Dict[str, Any], 
    reindex: bool = False,
    date_range: Optional[tuple] = None
) -> Dict[str, Any]:
    """Score all memories and update the index."""
    memory_dir = Path(config['memory_dir']).expanduser()
    
    # Load existing index
    if reindex:
        memory_index = {"memories": {}, "last_updated": None, "version": "1.0"}
    else:
        memory_index = load_memory_index(memory_dir)
    
    # Get memory files
    memory_files = get_memory_files(memory_dir, date_range)
    
    if not memory_files:
        print("No memory files found")
        return memory_index
    
    # Read all memory files and extract memories
    all_memories = []
    file_memories_map = {}
    
    for file_path in memory_files:
        file_data = read_memory_file(file_path)
        memories = extract_memories_from_file(file_data)
        
        all_memories.extend(memories)
        file_memories_map[str(file_path)] = memories
    
    print(f"Found {len(all_memories)} memories in {len(memory_files)} files")
    
    # Calculate frequency scores
    frequency_scores = calculate_frequency_scores(all_memories)
    
    # Score each memory
    scored_memories = {}
    reference_date = datetime.now()
    
    for memory in all_memories:
        # Add frequency info
        memory_id = memory['id']
        memory['frequency'] = frequency_scores.get(memory_id, 1)
        
        # Calculate score
        score = calculate_memory_score(memory, config, reference_date)
        memory['score'] = score
        
        # Store in index
        scored_memories[memory_id] = {
            'text': memory['text'][:200] + '...' if len(memory['text']) > 200 else memory['text'],
            'category': memory['category'],
            'source_file': memory['source_file'],
            'score': score,
            'timestamp': memory['timestamp'].isoformat() if isinstance(memory['timestamp'], datetime) else str(memory['timestamp']),
            'frequency': memory['frequency'],
            'last_scored': reference_date.isoformat()
        }
    
    # Update memory index
    memory_index['memories'] = scored_memories
    memory_index['last_updated'] = reference_date.isoformat()
    memory_index['stats'] = {
        'total_memories': len(scored_memories),
        'total_files': len(memory_files),
        'score_distribution': calculate_score_distribution(scored_memories),
        'category_distribution': calculate_category_distribution(all_memories),
        'avg_score': sum(m['score'] for m in scored_memories.values()) / len(scored_memories) if scored_memories else 0
    }
    
    # Calculate entity scores
    entity_scores = calculate_entity_scores(all_memories)
    memory_index['entity_scores'] = entity_scores
    
    # Save index
    save_memory_index(memory_dir, memory_index)
    
    return memory_index


def calculate_score_distribution(scored_memories: Dict[str, Any]) -> Dict[str, int]:
    """Calculate distribution of scores in buckets."""
    buckets = {
        '0.0-0.5': 0,
        '0.5-1.0': 0,
        '1.0-1.5': 0,
        '1.5-2.0': 0,
        '2.0-2.5': 0,
        '2.5-3.0': 0,
        '3.0+': 0
    }
    
    for memory_data in scored_memories.values():
        score = memory_data.get('score', 0)
        
        if score < 0.5:
            buckets['0.0-0.5'] += 1
        elif score < 1.0:
            buckets['0.5-1.0'] += 1
        elif score < 1.5:
            buckets['1.0-1.5'] += 1
        elif score < 2.0:
            buckets['1.5-2.0'] += 1
        elif score < 2.5:
            buckets['2.0-2.5'] += 1
        elif score < 3.0:
            buckets['2.5-3.0'] += 1
        else:
            buckets['3.0+'] += 1
    
    return buckets


def show_top_memories(memory_index: Dict[str, Any], limit: int = 20) -> None:
    """Display top-scored memories."""
    memories = memory_index.get('memories', {})
    
    if not memories:
        print("No memories found in index")
        return
    
    # Sort by score
    sorted_memories = sorted(
        memories.items(),
        key=lambda x: x[1].get('score', 0),
        reverse=True
    )
    
    print(f"🏆 Top {min(limit, len(sorted_memories))} Highest-Scored Memories")
    print("=" * 60)
    
    for i, (memory_id, memory_data) in enumerate(sorted_memories[:limit], 1):
        score = memory_data.get('score', 0)
        category = memory_data.get('category', 'unknown')
        text = memory_data.get('text', '')
        source = Path(memory_data.get('source_file', '')).name
        
        print(f"\n{i:2d}. Score: {score:.2f} | Category: {category}")
        print(f"    Source: {source}")
        print(f"    Text: {text}")


def show_memory_stats(memory_index: Dict[str, Any]) -> None:
    """Display memory statistics."""
    stats = memory_index.get('stats', {})
    last_updated = memory_index.get('last_updated')
    
    print("📊 Memory Index Statistics")
    print("=" * 40)
    
    if last_updated:
        update_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        print(f"Last Updated: {update_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"Total Memories: {stats.get('total_memories', 0):,}")
    print(f"Total Files: {stats.get('total_files', 0)}")
    print(f"Average Score: {stats.get('avg_score', 0):.3f}")
    
    # Score distribution
    score_dist = stats.get('score_distribution', {})
    if score_dist:
        print("\nScore Distribution:")
        for bucket, count in score_dist.items():
            if count > 0:
                print(f"  {bucket}: {count}")
    
    # Category distribution
    category_dist = stats.get('category_distribution', {})
    if category_dist:
        print("\nCategory Distribution:")
        sorted_categories = sorted(category_dist.items(), key=lambda x: x[1], reverse=True)
        for category, count in sorted_categories:
            print(f"  {category}: {count}")
    
    # Top entities
    entity_scores = memory_index.get('entity_scores', {})
    if entity_scores:
        print("\nTop Entities:")
        sorted_entities = sorted(entity_scores.items(), key=lambda x: x[1], reverse=True)
        for entity, score in sorted_entities[:10]:
            print(f"  {entity}: {score:.2f}")


def decay_memories(
    memory_index: Dict[str, Any],
    config: Dict[str, Any],
    days: int = 1
) -> Dict[str, Any]:
    """Apply time decay to all memories."""
    scoring_config = config.get('scoring', {})
    decay_half_life = scoring_config.get('decay_half_life_days', 14)
    
    if days <= 0:
        return memory_index
    
    # Calculate decay factor
    decay_factor = 0.5 ** (days / decay_half_life)
    
    memories = memory_index.get('memories', {})
    decayed_count = 0
    
    for memory_id, memory_data in memories.items():
        if 'score' in memory_data:
            old_score = memory_data['score']
            memory_data['score'] = old_score * decay_factor
            memory_data['last_decayed'] = datetime.now().isoformat()
            decayed_count += 1
    
    print(f"Applied {days} day(s) decay to {decayed_count} memories (factor: {decay_factor:.4f})")
    
    # Update stats
    if 'stats' in memory_index:
        memories_list = list(memories.values())
        memory_index['stats']['avg_score'] = (
            sum(m['score'] for m in memories_list) / len(memories_list) 
            if memories_list else 0
        )
        memory_index['stats']['score_distribution'] = calculate_score_distribution(memories)
    
    return memory_index


def filter_low_scoring_memories(
    memory_index: Dict[str, Any],
    min_score: float = 0.1
) -> Dict[str, Any]:
    """Remove memories below score threshold."""
    memories = memory_index.get('memories', {})
    
    filtered_memories = {
        memory_id: memory_data
        for memory_id, memory_data in memories.items()
        if memory_data.get('score', 0) >= min_score
    }
    
    removed_count = len(memories) - len(filtered_memories)
    print(f"Filtered {removed_count} memories below score {min_score}")
    
    memory_index['memories'] = filtered_memories
    
    # Update stats
    if 'stats' in memory_index:
        memory_index['stats']['total_memories'] = len(filtered_memories)
        if filtered_memories:
            memory_index['stats']['avg_score'] = (
                sum(m['score'] for m in filtered_memories.values()) / len(filtered_memories)
            )
        memory_index['stats']['score_distribution'] = calculate_score_distribution(filtered_memories)
    
    return memory_index


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Score memories and manage memory index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 score.py --reindex                   # Rebuild entire index
  python3 score.py --show-top 10              # Show top 10 memories
  python3 score.py --stats                    # Show statistics
  python3 score.py --decay 7                  # Apply 7 days of decay
  python3 score.py --filter 0.5               # Remove memories below 0.5
        """
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--reindex',
        action='store_true',
        help='Rebuild the entire memory index from scratch'
    )
    
    parser.add_argument(
        '--update-only',
        action='store_true',
        help='Update scores without rebuilding index'
    )
    
    parser.add_argument(
        '--show-top',
        type=int,
        metavar='N',
        help='Show top N highest-scored memories'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show memory index statistics'
    )
    
    parser.add_argument(
        '--decay',
        type=int,
        metavar='DAYS',
        help='Apply time decay for N days'
    )
    
    parser.add_argument(
        '--filter',
        type=float,
        metavar='MIN_SCORE',
        help='Remove memories below minimum score'
    )
    
    parser.add_argument(
        '--date-range',
        help='Process only files in date range (YYYY-MM-DD,YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--output-json',
        type=Path,
        help='Export memory index to JSON file'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        memory_dir = Path(config['memory_dir']).expanduser()
        
        # Parse date range if provided
        date_range = None
        if args.date_range:
            try:
                start_str, end_str = args.date_range.split(',')
                start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
                end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
                date_range = (start_date, end_date)
            except ValueError:
                print("Error: Invalid date range format. Use YYYY-MM-DD,YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
        
        # Determine action
        if args.reindex or args.update_only:
            print("🔄 Scoring memories...")
            memory_index = score_all_memories(config, args.reindex, date_range)
            print("✅ Memory scoring complete")
        else:
            memory_index = load_memory_index(memory_dir)
        
        # Apply decay if requested
        if args.decay:
            memory_index = decay_memories(memory_index, config, args.decay)
            save_memory_index(memory_dir, memory_index)
        
        # Filter if requested
        if args.filter:
            memory_index = filter_low_scoring_memories(memory_index, args.filter)
            save_memory_index(memory_dir, memory_index)
        
        # Show results
        if args.show_top:
            show_top_memories(memory_index, args.show_top)
        elif args.stats:
            show_memory_stats(memory_index)
        elif not (args.reindex or args.update_only or args.decay or args.filter):
            # Default: show brief stats
            show_memory_stats(memory_index)
        
        # Export if requested
        if args.output_json:
            with open(args.output_json, 'w') as f:
                json.dump(memory_index, f, indent=2, default=str)
            print(f"📄 Memory index exported to: {args.output_json}")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()