#!/usr/bin/env python3
"""Incremental consolidation of daily logs into canonical MEMORY.md (local Ollama)."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import re
import subprocess
import sys

sys.path.append(str(Path(__file__).parent))
from utils.indexer import build_or_update_index
from utils.memory_io import estimate_tokens, gather_memory_files, load_config, read_text, write_text
from utils.ollama_client import OllamaService


HEADER = "## Recent Consolidations"


def _recent_daily(config, days: int):
    today = datetime.utcnow().date()
    items = []
    for e in gather_memory_files(config, scope="shared"):
        if e["kind"] != "daily":
            continue
        try:
            d = datetime.strptime(e["path"].stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= (today - timedelta(days=days)):
            items.append(e["path"])
    return sorted(items)


def _summarize_daily(ollama: OllamaService, files: list[Path]) -> str:
    merged = []
    for p in files:
        merged.append(f"# {p.name}\n" + read_text(p)[:9000])
    prompt = (
        "Summarize these daily logs for MEMORY.md incremental update. "
        "Output markdown bullets grouped under: Decisions, Facts, Preferences, Action Items. "
        "Keep concise and factual.\n\n" + "\n\n".join(merged)
    )
    return ollama.generate(prompt, temperature=0.0)


def _merge(memory_text: str, summary_text: str, stamp: str) -> str:
    block = f"\n### {stamp}\n{summary_text.strip()}\n"
    if HEADER not in memory_text:
        return memory_text.rstrip() + f"\n\n{HEADER}\n" + block
    return re.sub(re.escape(HEADER), HEADER + block, memory_text, count=1)


def _should_compact(cfg, text: str) -> bool:
    c = cfg["compaction"]
    over_bytes = len(text.encode("utf-8")) >= int(c.get("max_memory_md_bytes", 240000))
    over_tokens = estimate_tokens(text) >= int(c.get("max_memory_md_tokens", 50000))
    weekly = False
    if c.get("weekly_schedule_enabled", True):
        target = c.get("weekly_day", "sunday").lower()
        weekly = datetime.utcnow().strftime("%A").lower() == target
    return over_bytes or over_tokens or weekly


def main() -> int:
    p = argparse.ArgumentParser(description="Consolidate recent daily logs into MEMORY.md")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--days", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    days = args.days or cfg.get("consolidation", {}).get("interval_days", 7)
    files = _recent_daily(cfg, days)
    if not files:
        print("No recent daily files found")
        return 0

    memory_md = Path(cfg["memory_md"]).expanduser()
    memory_text = read_text(memory_md) if memory_md.exists() else "# MEMORY\n"

    ollama = OllamaService(
        host=cfg["ollama"]["host"],
        embedding_model=cfg["ollama"]["embedding_model"],
        generation_model=cfg["ollama"]["generation_model"],
    )
    summary = _summarize_daily(ollama, files)
    merged = _merge(memory_text, summary, datetime.utcnow().strftime("%Y-%m-%d"))

    if args.dry_run and not args.apply:
        print(f"Dry run: {len(files)} daily logs would be consolidated into {memory_md}")
        print(f"New MEMORY.md bytes: {len(merged.encode('utf-8'))}")
    else:
        write_text(memory_md, merged)
        print(f"Updated {memory_md}")

    if _should_compact(cfg, merged):
        print("Compaction trigger met.")
        cmd = [sys.executable, str(Path(__file__).parent / "memory_compact.py"), "--config", args.config]
        if args.dry_run and not args.apply:
            cmd.append("--dry-run")
        else:
            cmd.extend(["--apply", "--reason", "consolidation_threshold"])
        subprocess.check_call(cmd)
    else:
        if not (args.dry_run and not args.apply):
            try:
                print(build_or_update_index(cfg, scope="all"))
            except RuntimeError as e:
                print(str(e))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
