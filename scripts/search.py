#!/usr/bin/env python3
"""Local semantic search using Ollama embeddings + FAISS."""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.indexer import search_index
from utils.memory_io import load_config


def _in_date_range(path: str, date_range: str | None) -> bool:
    if not date_range:
        return True
    try:
        start_s, end_s = [x.strip() for x in date_range.split(",", 1)]
        start = datetime.strptime(start_s, "%Y-%m-%d").date()
        end = datetime.strptime(end_s, "%Y-%m-%d").date()
    except ValueError:
        return True

    m = re.search(r"(\d{4}-\d{2}-\d{2})", path)
    if not m:
        return True
    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        return start <= d <= end
    except ValueError:
        return True


def main() -> int:
    p = argparse.ArgumentParser(description="Search local memory index")
    p.add_argument("query")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--scope", default="shared", help="shared|all|agent:<name>")
    p.add_argument("--agent", default=os.environ.get("OPENCLAW_AGENT"))
    p.add_argument("--date-range", default=None)
    p.add_argument("--format", choices=["text", "json"], default="text")
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    scope = args.scope
    if scope == "agent" and args.agent:
        scope = f"agent:{args.agent}"

    try:
        results = search_index(cfg, args.query, args.limit, scope=scope, agent=args.agent)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    results = [r for r in results if _in_date_range(r["file_path"], args.date_range)]

    if args.format == "json":
        print(json.dumps(results, indent=2))
        return 0

    print(f"Query: {args.query}")
    print(f"Scope: {scope}")
    print(f"Results: {len(results)}")
    for i, r in enumerate(results, start=1):
        print(f"\n{i}. {r['file_path']}:{r['start_line']}-{r['end_line']} score={r['score']:.4f}")
        print(f"   {r['snippet'].replace(chr(10), ' ')[:240]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
