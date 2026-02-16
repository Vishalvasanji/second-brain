#!/usr/bin/env python3
"""
Nightly Memory Pipeline for Second Brain v2

Orchestrates the full memory processing pipeline: extract → score → consolidate → index.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add utils to path
sys.path.append(str(Path(__file__).parent))

from utils.memory_io import (
    load_config, append_pipeline_log, find_session_files, ensure_memory_dir
)
from utils.qmd_bridge import QMDSearcher


class PipelineRunner:
    """Manages the memory processing pipeline."""
    
    def __init__(self, config: Dict[str, Any], dry_run: bool = False, verbose: bool = False):
        """Initialize pipeline runner."""
        self.config = config
        self.dry_run = dry_run
        self.verbose = verbose
        
        self.memory_dir = Path(config['memory_dir']).expanduser()
        self.session_dir = Path(config['session_dir']).expanduser()
        self.scripts_dir = Path(__file__).parent
        
        # Pipeline results
        self.results = {
            'started_at': datetime.now().isoformat(),
            'dry_run': dry_run,
            'steps': {}
        }
        
        ensure_memory_dir(self.memory_dir)
    
    def log(self, message: str, level: str = 'info') -> None:
        """Log a message."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        prefix = f"[{timestamp}] "
        
        if level == 'error':
            prefix += "❌ "
        elif level == 'warning':
            prefix += "⚠️  "
        elif level == 'success':
            prefix += "✅ "
        else:
            prefix += "ℹ️  "
        
        print(f"{prefix}{message}")
    
    def run_script(self, script_name: str, args: List[str] = None) -> Dict[str, Any]:
        """Run a pipeline script and return results."""
        if args is None:
            args = []
        
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            return {
                'success': False,
                'error': f"Script not found: {script_path}",
                'output': '',
                'returncode': -1
            }
        
        # Build command
        cmd = [sys.executable, str(script_path)] + args
        
        # Only pass --dry-run to scripts that support it (not score.py, stats.py)
        dry_run_scripts = {'consolidate.py', 'pipeline.py', 'extract_v2.py'}
        if self.dry_run and '--dry-run' not in args and script_name in dry_run_scripts:
            cmd.append('--dry-run')
        
        if self.verbose and '--verbose' not in args:
            cmd.append('--verbose')
        
        self.log(f"Running: {script_name} {' '.join(args)}")
        
        try:
            # Run the script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.get('pipeline', {}).get('max_runtime_minutes', 30) * 60,
                cwd=self.scripts_dir
            )
            
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'output': result.stdout,
                'error': result.stderr,
                'command': ' '.join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Script timed out',
                'output': '',
                'returncode': -999
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'output': '',
                'returncode': -1
            }
    
    def step_extract_recent(self) -> bool:
        """Step 1: Extract memories from recent sessions."""
        pipeline_config = self.config.get('pipeline', {})
        
        if not pipeline_config.get('extract_recent', True):
            self.log("Skipping extraction (disabled in config)")
            return True
        
        # Find sessions from yesterday and today
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        
        sessions_found = 0
        for target_date in [yesterday, today]:
            session_files = find_session_files(self.session_dir, target_date)
            sessions_found += len(session_files)
            
            if session_files:
                self.log(f"Found {len(session_files)} session(s) for {target_date}")
                
                # Run extraction for this date
                args = ['--date', str(target_date)]
                if self.config.get('extraction', {}).get('structured_output', True):
                    args.append('--structured')
                
                result = self.run_script('extract_v2.py', args)
                
                step_key = f'extract_{target_date}'
                self.results['steps'][step_key] = result
                
                if not result['success']:
                    self.log(f"Extraction failed for {target_date}: {result.get('error', 'Unknown error')}", 'error')
                    return False
                else:
                    self.log(f"Extraction completed for {target_date}", 'success')
        
        if sessions_found == 0:
            self.log("No recent sessions found to extract")
        
        return True
    
    def step_update_scores(self) -> bool:
        """Step 2: Update memory scores."""
        pipeline_config = self.config.get('pipeline', {})
        
        if not pipeline_config.get('update_scores', True):
            self.log("Skipping score update (disabled in config)")
            return True
        
        self.log("Updating memory scores...")
        
        # Run scoring with update-only (don't rebuild entire index)
        result = self.run_script('score.py', ['--update-only'])
        self.results['steps']['score_update'] = result
        
        if not result['success']:
            self.log(f"Score update failed: {result.get('error', 'Unknown error')}", 'error')
            return False
        else:
            self.log("Memory scores updated", 'success')
            return True
    
    def step_update_search_index(self) -> bool:
        """Step 3: Update search indexes (qmd, etc.)."""
        pipeline_config = self.config.get('pipeline', {})
        
        if not pipeline_config.get('update_qmd', True):
            self.log("Skipping search index update (disabled in config)")
            return True
        
        # Try to update qmd if available
        qmd_searcher = QMDSearcher()
        
        if qmd_searcher.available:
            self.log("Updating qmd search index...")
            
            success = True
            
            # Update file index
            if qmd_searcher.update_index():
                self.log("qmd file index updated", 'success')
            else:
                self.log("qmd file index update failed", 'warning')
                success = False
            
            # Update embeddings (for semantic search)
            if qmd_searcher.rebuild_embeddings():
                self.log("qmd embeddings updated", 'success')
            else:
                self.log("qmd embeddings update failed", 'warning')
                success = False
            
            self.results['steps']['qmd_update'] = {
                'success': success,
                'available': True
            }
        else:
            self.log("qmd not available, skipping search index update", 'warning')
            self.results['steps']['qmd_update'] = {
                'success': True,  # Not a failure if qmd isn't available
                'available': False
            }
        
        return True
    
    def step_consolidate(self) -> bool:
        """Step 4: Auto-consolidate memories (if enabled and threshold met)."""
        pipeline_config = self.config.get('pipeline', {})
        consolidation_config = self.config.get('consolidation', {})
        
        # Check if consolidation is enabled
        if not pipeline_config.get('consolidate', False):
            self.log("Skipping consolidation (disabled in config)")
            return True
        
        # Check consolidation threshold
        threshold = pipeline_config.get('consolidate_threshold', 5)
        
        # Count recent memory files to see if we meet threshold
        end_date = date.today()
        start_date = end_date - timedelta(days=consolidation_config.get('interval_days', 7))
        
        from utils.memory_io import get_memory_files
        recent_files = get_memory_files(self.memory_dir, (start_date, end_date))
        
        if len(recent_files) < threshold:
            self.log(f"Consolidation threshold not met ({len(recent_files)} < {threshold} files)")
            return True
        
        self.log(f"Running consolidation ({len(recent_files)} recent files)...")
        
        # Run consolidation
        args = [
            '--days', str(consolidation_config.get('interval_days', 7))
        ]
        
        # Always use dry-run in pipeline unless explicitly configured otherwise
        pipeline_dry_run = consolidation_config.get('dry_run', True)
        if not pipeline_dry_run and not self.dry_run:
            args.append('--apply')
        # else: will default to dry-run
        
        result = self.run_script('consolidate.py', args)
        self.results['steps']['consolidate'] = result
        
        if not result['success']:
            self.log(f"Consolidation failed: {result.get('error', 'Unknown error')}", 'error')
            return False
        else:
            action = "completed" if not pipeline_dry_run and not self.dry_run else "simulated"
            self.log(f"Consolidation {action}", 'success')
            return True
    
    def step_generate_report(self) -> bool:
        """Step 5: Generate pipeline report."""
        pipeline_config = self.config.get('pipeline', {})
        
        if not pipeline_config.get('generate_report', True):
            self.log("Skipping report generation (disabled in config)")
            return True
        
        self.log("Generating pipeline report...")
        
        # Run stats to get current memory status
        result = self.run_script('stats.py', ['--format', 'json'])
        
        if result['success']:
            try:
                stats_data = json.loads(result['output'])
                self.results['memory_stats'] = stats_data
            except json.JSONDecodeError:
                self.log("Failed to parse stats output", 'warning')
        
        # Generate summary report
        report = self.generate_summary_report()
        
        # Save report to memory directory
        report_path = self.memory_dir / f".pipeline-report-{datetime.now().strftime('%Y-%m-%d')}.json"
        
        try:
            with open(report_path, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            self.log(f"Pipeline report saved: {report_path}")
            
            # Also print summary to stdout
            print("\n" + "="*60)
            print("📊 PIPELINE SUMMARY")
            print("="*60)
            print(report)
            
        except Exception as e:
            self.log(f"Failed to save pipeline report: {e}", 'error')
            return False
        
        return True
    
    def generate_summary_report(self) -> str:
        """Generate human-readable pipeline summary."""
        lines = []
        
        # Header
        started = datetime.fromisoformat(self.results['started_at'])
        duration = datetime.now() - started
        
        lines.append(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Duration: {duration.total_seconds():.1f} seconds")
        lines.append(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        lines.append("")
        
        # Step results
        lines.append("Step Results:")
        steps = self.results.get('steps', {})
        
        for step_name, step_result in steps.items():
            success = step_result.get('success', False)
            status = "✅" if success else "❌"
            lines.append(f"  {status} {step_name.replace('_', ' ').title()}")
            
            if not success:
                error = step_result.get('error', 'Unknown error')
                lines.append(f"      Error: {error}")
        
        # Memory stats if available
        if 'memory_stats' in self.results:
            stats = self.results['memory_stats']
            lines.append("")
            lines.append("Current Memory Status:")
            lines.append(f"  Total memories: {stats.get('total_memories', 0):,}")
            lines.append(f"  Total files: {stats.get('total_files', 0)}")
            lines.append(f"  Average score: {stats.get('avg_score', 0):.3f}")
        
        # Recommendations
        lines.append("")
        lines.append("Recommendations:")
        
        failed_steps = [name for name, result in steps.items() if not result.get('success')]
        if failed_steps:
            lines.append(f"  ⚠️  {len(failed_steps)} step(s) failed - check logs")
        
        qmd_result = steps.get('qmd_update', {})
        if not qmd_result.get('available'):
            lines.append("  💡 Install qmd for better search performance")
        
        if self.dry_run:
            lines.append("  🔄 Run without --dry-run to apply changes")
        
        return "\n".join(lines)
    
    def run_pipeline(self) -> bool:
        """Run the complete pipeline."""
        self.log(f"🚀 Starting memory pipeline ({'dry-run' if self.dry_run else 'live mode'})")
        
        # Record pipeline start
        self.results['started_at'] = datetime.now().isoformat()
        
        steps = [
            ("Extract Recent Sessions", self.step_extract_recent),
            ("Update Memory Scores", self.step_update_scores), 
            ("Update Search Index", self.step_update_search_index),
            ("Consolidate Memories", self.step_consolidate),
            ("Generate Report", self.step_generate_report)
        ]
        
        success = True
        for step_name, step_func in steps:
            try:
                self.log(f"Starting: {step_name}")
                
                if not step_func():
                    self.log(f"Step failed: {step_name}", 'error')
                    success = False
                    break  # Stop on first failure
                    
            except Exception as e:
                self.log(f"Step crashed: {step_name} - {e}", 'error')
                success = False
                break
        
        # Record completion
        self.results['completed_at'] = datetime.now().isoformat()
        self.results['success'] = success
        
        # Log to pipeline history
        append_pipeline_log(self.memory_dir, {
            'success': success,
            'duration_seconds': (datetime.now() - datetime.fromisoformat(self.results['started_at'])).total_seconds(),
            'steps_completed': len([s for s in self.results['steps'].values() if s.get('success')]),
            'steps_failed': len([s for s in self.results['steps'].values() if not s.get('success')]),
            'dry_run': self.dry_run
        })
        
        if success:
            self.log("🎉 Pipeline completed successfully!", 'success')
        else:
            self.log("💥 Pipeline failed", 'error')
        
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run the nightly memory processing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 pipeline.py                    # Run pipeline in dry-run mode
  python3 pipeline.py --apply            # Run pipeline and apply changes
  python3 pipeline.py --dry-run --verbose # Preview with detailed output
  python3 pipeline.py --skip-extract     # Skip session extraction
        """
    )
    
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Preview mode - do not apply changes (default)'
    )
    
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply changes (overrides --dry-run)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    
    parser.add_argument(
        '--skip-extract',
        action='store_true',
        help='Skip session extraction step'
    )
    
    parser.add_argument(
        '--skip-consolidate',
        action='store_true',
        help='Skip memory consolidation step'
    )
    
    parser.add_argument(
        '--force-consolidate',
        action='store_true',
        help='Force consolidation regardless of threshold'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Override config based on args
        pipeline_config = config.setdefault('pipeline', {})
        
        if args.skip_extract:
            pipeline_config['extract_recent'] = False
        
        if args.skip_consolidate:
            pipeline_config['consolidate'] = False
        
        if args.force_consolidate:
            pipeline_config['consolidate'] = True
            pipeline_config['consolidate_threshold'] = 0
        
        # Determine run mode
        dry_run = args.dry_run and not args.apply
        
        # Run pipeline
        runner = PipelineRunner(config, dry_run, args.verbose)
        success = runner.run_pipeline()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Pipeline interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Pipeline failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()