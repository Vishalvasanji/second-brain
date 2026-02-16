#!/usr/bin/env python3
"""
Memory Health Dashboard for Second Brain v2

Track memory growth, coverage gaps, and system health metrics.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add utils to path
sys.path.append(str(Path(__file__).parent))

from utils.memory_io import (
    load_config, get_memory_files, read_memory_file,
    load_memory_index, load_pipeline_log
)


class MemoryStatsCollector:
    """Collects and analyzes memory statistics."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize stats collector."""
        self.config = config
        self.memory_dir = Path(config['memory_dir']).expanduser()
        self.memory_md_path = Path(config['memory_md']).expanduser()
        
        # Load data
        self.memory_files = get_memory_files(self.memory_dir)
        self.memory_index = load_memory_index(self.memory_dir)
        self.pipeline_log = load_pipeline_log(self.memory_dir)
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """Get basic memory statistics."""
        stats = {
            'total_files': len(self.memory_files),
            'total_size_bytes': 0,
            'oldest_file': None,
            'newest_file': None,
            'memory_md_exists': self.memory_md_path.exists(),
            'memory_md_size': 0,
            'memory_md_last_modified': None
        }
        
        # Analyze memory files
        file_dates = []
        for file_path in self.memory_files:
            try:
                stat = file_path.stat()
                stats['total_size_bytes'] += stat.st_size
                
                # Try to parse date from filename
                try:
                    file_date = datetime.strptime(file_path.stem, "%Y-%m-%d").date()
                    file_dates.append(file_date)
                except ValueError:
                    # Not a date-formatted file
                    pass
                    
            except OSError:
                continue
        
        # Date range
        if file_dates:
            stats['oldest_file'] = min(file_dates)
            stats['newest_file'] = max(file_dates)
            stats['date_range_days'] = (max(file_dates) - min(file_dates)).days
        
        # MEMORY.md stats
        if stats['memory_md_exists']:
            try:
                stat = self.memory_md_path.stat()
                stats['memory_md_size'] = stat.st_size
                stats['memory_md_last_modified'] = datetime.fromtimestamp(stat.st_mtime)
            except OSError:
                stats['memory_md_exists'] = False
        
        return stats
    
    def get_memory_growth_stats(self) -> Dict[str, Any]:
        """Analyze memory growth over time."""
        # Group files by date
        files_by_date = defaultdict(list)
        
        for file_path in self.memory_files:
            try:
                file_date = datetime.strptime(file_path.stem, "%Y-%m-%d").date()
                files_by_date[file_date].append(file_path)
            except ValueError:
                continue
        
        if not files_by_date:
            return {'error': 'No date-formatted memory files found'}
        
        # Calculate growth metrics
        dates = sorted(files_by_date.keys())
        daily_counts = [len(files_by_date[d]) for d in dates]
        
        # Find gaps (missing days)
        if len(dates) >= 2:
            date_range = (dates[-1] - dates[0]).days + 1
            expected_dates = {dates[0] + timedelta(days=i) for i in range(date_range)}
            actual_dates = set(dates)
            missing_dates = sorted(expected_dates - actual_dates)
        else:
            missing_dates = []
        
        # Recent activity (last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        recent_dates = [d for d in dates if d >= thirty_days_ago]
        
        return {
            'total_days': len(dates),
            'date_range': {
                'start': dates[0] if dates else None,
                'end': dates[-1] if dates else None,
                'span_days': (dates[-1] - dates[0]).days if len(dates) >= 2 else 0
            },
            'missing_days': len(missing_dates),
            'coverage_percentage': (len(dates) / ((dates[-1] - dates[0]).days + 1) * 100) if len(dates) >= 2 else 100,
            'files_per_day': {
                'avg': sum(daily_counts) / len(daily_counts) if daily_counts else 0,
                'min': min(daily_counts) if daily_counts else 0,
                'max': max(daily_counts) if daily_counts else 0
            },
            'recent_activity': {
                'days_with_memories': len(recent_dates),
                'days_possible': min(30, (date.today() - dates[0]).days + 1) if dates else 0
            },
            'gaps': missing_dates[:10]  # Show first 10 gaps
        }
    
    def get_content_stats(self) -> Dict[str, Any]:
        """Analyze memory content statistics."""
        total_memories = 0
        category_counts = Counter()
        section_counts = Counter()
        total_content_length = 0
        
        # Analyze each file
        for file_path in self.memory_files:
            try:
                file_data = read_memory_file(file_path)
                sections = file_data.get('sections', {})
                content = file_data.get('content', '')
                
                total_content_length += len(content)
                
                for section_name, items in sections.items():
                    section_counts[section_name] += 1
                    total_memories += len(items)
                    
                    # Categorize items
                    for item in items:
                        # Simple categorization based on content
                        if section_name == 'people_mentioned':
                            category_counts['people'] += 1
                        elif 'decision' in section_name:
                            category_counts['decisions'] += 1
                        elif 'action' in section_name:
                            category_counts['actions'] += 1
                        elif 'technical' in section_name:
                            category_counts['technical'] += 1
                        elif 'fact' in section_name or 'preference' in section_name:
                            category_counts['facts'] += 1
                        else:
                            category_counts['other'] += 1
                            
            except Exception:
                continue  # Skip problematic files
        
        return {
            'total_memories': total_memories,
            'total_content_chars': total_content_length,
            'avg_content_per_file': total_content_length / len(self.memory_files) if self.memory_files else 0,
            'avg_memories_per_file': total_memories / len(self.memory_files) if self.memory_files else 0,
            'category_distribution': dict(category_counts.most_common()),
            'section_distribution': dict(section_counts.most_common()),
            'most_common_sections': section_counts.most_common(10)
        }
    
    def get_scoring_stats(self) -> Dict[str, Any]:
        """Get memory scoring statistics."""
        index_stats = self.memory_index.get('stats', {})
        memories = self.memory_index.get('memories', [])
        
        if not memories:
            return {'error': 'No scored memories found'}
        
        # Support both list and dict formats
        memory_list = memories if isinstance(memories, list) else memories.values()
        
        # Analyze scores
        scores = [m.get('score', 0) for m in memory_list]
        scores.sort()
        
        # Calculate percentiles
        def percentile(data, p):
            k = (len(data) - 1) * p / 100
            f = int(k)
            c = k - f
            if f == len(data) - 1:
                return data[f]
            return data[f] * (1 - c) + data[f + 1] * c
        
        score_stats = {
            'total_scored_memories': len(scores),
            'score_range': {
                'min': min(scores),
                'max': max(scores),
                'mean': sum(scores) / len(scores),
                'median': percentile(scores, 50),
                'p90': percentile(scores, 90),
                'p99': percentile(scores, 99)
            },
            'score_distribution': index_stats.get('score_distribution', {}),
            'last_updated': self.memory_index.get('last_updated'),
            'entity_scores': len(self.memory_index.get('entity_scores', {}))
        }
        
        # Analyze score decay over time
        scored_by_date = defaultdict(list)
        for memory in memory_list:
            timestamp = memory.get('timestamp')
            if timestamp:
                try:
                    memory_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).date()
                    scored_by_date[memory_date].append(memory.get('score', 0))
                except Exception:
                    continue
        
        # Average score by date (last 30 days)
        thirty_days_ago = date.today() - timedelta(days=30)
        recent_scores_by_date = {
            d: sum(scores) / len(scores) if scores else 0
            for d, scores in scored_by_date.items()
            if d >= thirty_days_ago
        }
        
        score_stats['recent_avg_scores_by_date'] = dict(sorted(recent_scores_by_date.items()))
        
        return score_stats
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline execution statistics."""
        if not self.pipeline_log:
            return {'error': 'No pipeline execution history found'}
        
        # Analyze recent pipeline runs
        total_runs = len(self.pipeline_log)
        successful_runs = len([r for r in self.pipeline_log if r.get('success')])
        
        # Recent runs (last 30)
        recent_runs = sorted(self.pipeline_log, key=lambda x: x.get('timestamp', ''))[-30:]
        recent_success_rate = len([r for r in recent_runs if r.get('success')]) / len(recent_runs) * 100 if recent_runs else 0
        
        # Average runtime
        runtimes = [r.get('duration_seconds', 0) for r in self.pipeline_log if r.get('duration_seconds')]
        avg_runtime = sum(runtimes) / len(runtimes) if runtimes else 0
        
        # Last run info
        last_run = recent_runs[-1] if recent_runs else None
        
        return {
            'total_runs': total_runs,
            'success_rate': successful_runs / total_runs * 100 if total_runs > 0 else 0,
            'recent_success_rate': recent_success_rate,
            'avg_runtime_seconds': avg_runtime,
            'last_run': {
                'timestamp': last_run.get('timestamp') if last_run else None,
                'success': last_run.get('success') if last_run else None,
                'duration': last_run.get('duration_seconds') if last_run else None
            } if last_run else None
        }
    
    def get_health_issues(self) -> List[Dict[str, str]]:
        """Identify potential health issues."""
        issues = []
        
        # Check for coverage gaps
        growth_stats = self.get_memory_growth_stats()
        if not growth_stats.get('error'):
            coverage = growth_stats.get('coverage_percentage', 100)
            if coverage < 80:
                issues.append({
                    'type': 'warning',
                    'category': 'coverage',
                    'message': f"Memory coverage is only {coverage:.1f}% - many missing days"
                })
            
            # Check for recent inactivity
            recent_activity = growth_stats.get('recent_activity', {})
            recent_days = recent_activity.get('days_with_memories', 0)
            possible_days = recent_activity.get('days_possible', 0)
            
            if possible_days > 0 and recent_days / possible_days < 0.5:
                issues.append({
                    'type': 'warning',
                    'category': 'activity',
                    'message': f"Low recent activity: only {recent_days} days with memories in last {possible_days} days"
                })
        
        # Check MEMORY.md freshness
        if self.memory_md_path.exists():
            try:
                stat = self.memory_md_path.stat()
                last_modified = datetime.fromtimestamp(stat.st_mtime)
                days_old = (datetime.now() - last_modified).days
                
                if days_old > 30:
                    issues.append({
                        'type': 'warning',
                        'category': 'consolidation',
                        'message': f"MEMORY.md hasn't been updated in {days_old} days - run consolidation"
                    })
            except OSError:
                pass
        else:
            issues.append({
                'type': 'error',
                'category': 'consolidation',
                'message': "MEMORY.md file doesn't exist - run consolidation"
            })
        
        # Check pipeline health
        pipeline_stats = self.get_pipeline_stats()
        if not pipeline_stats.get('error'):
            success_rate = pipeline_stats.get('recent_success_rate', 100)
            if success_rate < 80:
                issues.append({
                    'type': 'error',
                    'category': 'pipeline',
                    'message': f"Pipeline success rate is only {success_rate:.1f}% - check logs"
                })
            
            last_run = pipeline_stats.get('last_run')
            if last_run and last_run.get('timestamp'):
                last_run_time = datetime.fromisoformat(last_run['timestamp'].replace('Z', '+00:00'))
                days_since = (datetime.now() - last_run_time).days
                
                if days_since > 2:
                    issues.append({
                        'type': 'warning',
                        'category': 'pipeline',
                        'message': f"Pipeline hasn't run in {days_since} days"
                    })
        
        # Check scoring freshness
        scoring_stats = self.get_scoring_stats()
        if not scoring_stats.get('error'):
            last_updated = scoring_stats.get('last_updated')
            if last_updated:
                try:
                    last_update_time = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    days_since = (datetime.now() - last_update_time).days
                    
                    if days_since > 7:
                        issues.append({
                            'type': 'warning',
                            'category': 'scoring',
                            'message': f"Memory scores haven't been updated in {days_since} days"
                        })
                except Exception:
                    pass
        
        return issues
    
    def collect_all_stats(self) -> Dict[str, Any]:
        """Collect all statistics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'basic': self.get_basic_stats(),
            'growth': self.get_memory_growth_stats(),
            'content': self.get_content_stats(),
            'scoring': self.get_scoring_stats(),
            'pipeline': self.get_pipeline_stats(),
            'health_issues': self.get_health_issues()
        }


def format_stats_text(stats: Dict[str, Any], detailed: bool = False) -> str:
    """Format statistics as human-readable text."""
    lines = []
    
    # Header
    lines.append("🧠 Memory System Health Dashboard")
    lines.append("=" * 50)
    
    timestamp = stats.get('timestamp')
    if timestamp:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        lines.append(f"Generated: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Basic stats
    basic = stats.get('basic', {})
    lines.append("📊 Basic Statistics")
    lines.append(f"  Total memory files: {basic.get('total_files', 0)}")
    lines.append(f"  Total size: {basic.get('total_size_bytes', 0) / 1024:.1f} KB")
    
    if basic.get('oldest_file') and basic.get('newest_file'):
        lines.append(f"  Date range: {basic['oldest_file']} to {basic['newest_file']}")
        lines.append(f"  Span: {basic.get('date_range_days', 0)} days")
    
    lines.append(f"  MEMORY.md: {'✅' if basic.get('memory_md_exists') else '❌'}")
    if basic.get('memory_md_last_modified'):
        mod_time = basic['memory_md_last_modified']
        if isinstance(mod_time, str):
            mod_time = datetime.fromisoformat(mod_time.replace('Z', '+00:00'))
        days_ago = (datetime.now() - mod_time).days
        lines.append(f"  MEMORY.md age: {days_ago} days")
    
    lines.append("")
    
    # Growth stats
    growth = stats.get('growth', {})
    if not growth.get('error'):
        lines.append("📈 Memory Growth")
        lines.append(f"  Coverage: {growth.get('coverage_percentage', 0):.1f}%")
        lines.append(f"  Missing days: {growth.get('missing_days', 0)}")
        
        recent = growth.get('recent_activity', {})
        lines.append(f"  Recent activity: {recent.get('days_with_memories', 0)}/{recent.get('days_possible', 0)} days")
        
        files_per_day = growth.get('files_per_day', {})
        lines.append(f"  Files per day: {files_per_day.get('avg', 0):.1f} avg")
        lines.append("")
    
    # Content stats
    content = stats.get('content', {})
    lines.append("📝 Content Statistics")
    lines.append(f"  Total memories: {content.get('total_memories', 0):,}")
    lines.append(f"  Avg memories/file: {content.get('avg_memories_per_file', 0):.1f}")
    lines.append(f"  Total content: {content.get('total_content_chars', 0):,} chars")
    
    # Top categories
    categories = content.get('category_distribution', {})
    if categories:
        lines.append("  Top categories:")
        for category, count in list(categories.items())[:5]:
            lines.append(f"    {category}: {count}")
    
    lines.append("")
    
    # Scoring stats
    scoring = stats.get('scoring', {})
    if not scoring.get('error'):
        lines.append("🎯 Memory Scoring")
        lines.append(f"  Scored memories: {scoring.get('total_scored_memories', 0):,}")
        
        score_range = scoring.get('score_range', {})
        lines.append(f"  Score range: {score_range.get('min', 0):.2f} - {score_range.get('max', 0):.2f}")
        lines.append(f"  Average score: {score_range.get('mean', 0):.3f}")
        lines.append(f"  Median score: {score_range.get('median', 0):.3f}")
        
        last_updated = scoring.get('last_updated')
        if last_updated:
            try:
                dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                days_ago = (datetime.now() - dt).days
                lines.append(f"  Last updated: {days_ago} days ago")
            except Exception:
                pass
        
        lines.append("")
    
    # Pipeline stats
    pipeline = stats.get('pipeline', {})
    if not pipeline.get('error'):
        lines.append("🔄 Pipeline Health")
        lines.append(f"  Total runs: {pipeline.get('total_runs', 0)}")
        lines.append(f"  Success rate: {pipeline.get('success_rate', 0):.1f}%")
        lines.append(f"  Recent success: {pipeline.get('recent_success_rate', 0):.1f}%")
        lines.append(f"  Avg runtime: {pipeline.get('avg_runtime_seconds', 0):.1f}s")
        
        last_run = pipeline.get('last_run')
        if last_run and last_run.get('timestamp'):
            try:
                dt = datetime.fromisoformat(last_run['timestamp'].replace('Z', '+00:00'))
                days_ago = (datetime.now() - dt).days
                status = "✅" if last_run.get('success') else "❌"
                lines.append(f"  Last run: {days_ago} days ago {status}")
            except Exception:
                pass
        
        lines.append("")
    
    # Health issues
    issues = stats.get('health_issues', [])
    if issues:
        lines.append("⚠️  Health Issues")
        for issue in issues:
            icon = "❌" if issue.get('type') == 'error' else "⚠️"
            lines.append(f"  {icon} {issue.get('message', 'Unknown issue')}")
        lines.append("")
    else:
        lines.append("✅ No health issues detected")
        lines.append("")
    
    # Recommendations
    lines.append("💡 Recommendations")
    
    if issues:
        error_count = len([i for i in issues if i.get('type') == 'error'])
        warning_count = len(issues) - error_count
        
        if error_count > 0:
            lines.append(f"  🔴 {error_count} critical issue(s) need immediate attention")
        if warning_count > 0:
            lines.append(f"  🟡 {warning_count} warning(s) should be addressed")
    
    # Specific recommendations based on stats
    if basic.get('total_files', 0) == 0:
        lines.append("  📥 No memory files found - run extract to get started")
    elif growth.get('coverage_percentage', 100) < 90:
        lines.append("  📅 Set up daily extraction to improve coverage")
    
    if not basic.get('memory_md_exists'):
        lines.append("  🗂  Run consolidation to create MEMORY.md")
    
    pipeline_success = pipeline.get('recent_success_rate', 100)
    if pipeline_success < 100:
        lines.append("  🔧 Check pipeline logs and fix failing components")
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Show memory system health statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 stats.py                    # Show basic health dashboard
  python3 stats.py --detailed         # Show detailed statistics
  python3 stats.py --format json      # Export as JSON
  python3 stats.py --issues-only      # Show only health issues
        """
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Show detailed statistics'
    )
    
    parser.add_argument(
        '--issues-only',
        action='store_true',
        help='Show only health issues'
    )
    
    parser.add_argument(
        '--export',
        type=Path,
        help='Export statistics to file'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Collect statistics
        collector = MemoryStatsCollector(config)
        stats = collector.collect_all_stats()
        
        # Handle issues-only mode
        if args.issues_only:
            issues = stats.get('health_issues', [])
            if not issues:
                print("✅ No health issues detected")
            else:
                print("⚠️  Health Issues Found:")
                for issue in issues:
                    icon = "❌" if issue.get('type') == 'error' else "⚠️"
                    category = issue.get('category', 'unknown')
                    message = issue.get('message', 'Unknown issue')
                    print(f"{icon} [{category}] {message}")
            return
        
        # Format output
        if args.format == 'json':
            output = json.dumps(stats, indent=2, default=str)
        else:
            output = format_stats_text(stats, args.detailed)
        
        # Export if requested
        if args.export:
            with open(args.export, 'w') as f:
                f.write(output)
            print(f"Statistics exported to: {args.export}")
        else:
            print(output)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()