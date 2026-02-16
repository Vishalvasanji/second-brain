#!/usr/bin/env python3
"""
qmd bridge for Second Brain v2

Integrates with the existing qmd search engine for better semantic search.
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import shlex


class QMDSearcher:
    """Bridge to qmd search engine."""
    
    def __init__(self, qmd_path: Optional[str] = None):
        """
        Initialize qmd searcher.
        
        Args:
            qmd_path: Path to qmd binary (auto-detected if None)
        """
        self.qmd_path = qmd_path or self._find_qmd_binary()
        self.available = self._check_availability()
        
    def _find_qmd_binary(self) -> str:
        """Find qmd binary in common locations."""
        common_paths = [
            "/Users/yajat/.bun/bin/qmd",
            "qmd",  # In PATH
            "/usr/local/bin/qmd",
            "/opt/homebrew/bin/qmd"
        ]
        
        for path in common_paths:
            try:
                result = subprocess.run([path, "--version"], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        return "qmd"  # Fallback to PATH
    
    def _check_availability(self) -> bool:
        """Check if qmd is available."""
        try:
            result = subprocess.run([self.qmd_path, "--version"], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def search(self, query: str, method: str = "query", limit: int = 10) -> List[Dict]:
        """
        Search using qmd.
        
        Args:
            query: Search query
            method: Search method ('search', 'vsearch', 'query')  
            limit: Maximum results
        
        Returns:
            List of search results
        """
        if not self.available:
            return []
        
        try:
            # Build command
            cmd = [self.qmd_path, method, query]
            
            # Run search
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                cwd=Path.home() / "workspace"  # Ensure we're in workspace
            )
            
            if result.returncode != 0:
                print(f"qmd search failed: {result.stderr}")
                return []
            
            # Parse results
            results = self._parse_qmd_output(result.stdout, limit)
            return results
            
        except subprocess.TimeoutExpired:
            print("qmd search timed out")
            return []
        except Exception as e:
            print(f"qmd search error: {e}")
            return []
    
    def _parse_qmd_output(self, output: str, limit: int) -> List[Dict]:
        """Parse qmd output into structured results."""
        results = []
        lines = output.strip().split('\n')
        
        current_result = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for file path (typically starts with memory/)  
            if line.startswith('memory/') or line.endswith('.md'):
                if current_result:
                    results.append(current_result)
                    if len(results) >= limit:
                        break
                
                current_result = {
                    'doc_id': line,
                    'path': line,
                    'content': '',
                    'highlights': [],
                    'score': 1.0  # qmd doesn't provide scores
                }
            elif current_result and line:
                # Content line
                if current_result['content']:
                    current_result['content'] += '\n' + line
                else:
                    current_result['content'] = line
                
                # Add as highlight if it looks meaningful
                if len(line) > 20 and not line.startswith('##'):
                    current_result['highlights'].append(line)
        
        # Don't forget the last result
        if current_result:
            results.append(current_result)
        
        return results[:limit]
    
    def update_index(self) -> bool:
        """Update qmd search index."""
        if not self.available:
            return False
        
        try:
            result = subprocess.run([self.qmd_path, "update"], 
                                  capture_output=True, text=True, timeout=60,
                                  cwd=Path.home() / "workspace")
            return result.returncode == 0
        except Exception as e:
            print(f"qmd update failed: {e}")
            return False
    
    def rebuild_embeddings(self) -> bool:
        """Rebuild qmd embeddings (for semantic search)."""
        if not self.available:
            return False
        
        try:
            result = subprocess.run([self.qmd_path, "embed"], 
                                  capture_output=True, text=True, timeout=300,
                                  cwd=Path.home() / "workspace")
            return result.returncode == 0
        except Exception as e:
            print(f"qmd embed failed: {e}")
            return False
    
    def get_collections(self) -> List[str]:
        """Get list of qmd collections."""
        if not self.available:
            return []
        
        try:
            result = subprocess.run([self.qmd_path, "collections"], 
                                  capture_output=True, text=True, timeout=10,
                                  cwd=Path.home() / "workspace")
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
        except Exception:
            pass
        
        return []


class HybridSearcher:
    """Hybrid searcher that combines qmd and BM25."""
    
    def __init__(self, qmd_searcher: QMDSearcher, bm25_searcher):
        """Initialize hybrid searcher."""
        self.qmd = qmd_searcher
        self.bm25 = bm25_searcher
        
    def search(self, query: str, limit: int = 10, method: str = "auto") -> List[Dict]:
        """
        Hybrid search using both qmd and BM25.
        
        Args:
            query: Search query
            limit: Maximum results
            method: Search method ('qmd', 'bm25', 'auto')
        
        Returns:
            Combined and deduplicated results
        """
        results = []
        
        # Try qmd first if available and method allows
        if method in ("qmd", "auto") and self.qmd.available:
            qmd_results = self.qmd.search(query, "query", limit)
            results.extend(qmd_results)
        
        # Use BM25 if qmd failed or method specifies
        if (not results and method in ("bm25", "auto")) or method == "bm25":
            bm25_results = self.bm25.search(query, limit)
            results.extend(bm25_results)
        
        # Deduplicate by doc_id/path
        seen = set()
        deduplicated = []
        
        for result in results:
            key = result.get('doc_id') or result.get('path')
            if key and key not in seen:
                seen.add(key)
                deduplicated.append(result)
        
        return deduplicated[:limit]
    
    def update_indexes(self) -> Dict[str, bool]:
        """Update all search indexes."""
        results = {}
        
        # Update qmd
        if self.qmd.available:
            results['qmd_update'] = self.qmd.update_index()
            results['qmd_embed'] = self.qmd.rebuild_embeddings()
        else:
            results['qmd_update'] = False
            results['qmd_embed'] = False
        
        # BM25 doesn't need explicit updates
        results['bm25'] = True
        
        return results


def create_hybrid_searcher(memory_files: List[Dict]) -> HybridSearcher:
    """Create a hybrid searcher with both qmd and BM25."""
    from .bm25 import create_memory_search_index
    
    # Create qmd searcher
    qmd_searcher = QMDSearcher()
    
    # Create BM25 searcher
    bm25_searcher = create_memory_search_index(memory_files)
    
    return HybridSearcher(qmd_searcher, bm25_searcher)