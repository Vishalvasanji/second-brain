#!/usr/bin/env python3
"""Local session extractor: writes high-frequency memory flushes to daily logs."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from utils.memory_io import load_config, write_text
from utils.ollama_client import OllamaService


def _latest_session(session_dir: Path) -> Path | None:
    files = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _load_session_text(path: Path) -> str:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        msg = obj.get("message", {})
        role = msg.get("role", obj.get("role", "unknown"))
        content = msg.get("content", obj.get("content", ""))
        if isinstance(content, list):
            content = "\n".join([x.get("text", "") for x in content if isinstance(x, dict)])
        lines.append(f"[{role}] {content}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Extract memory notes from recent session jsonl")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--session", default=None)
    p.add_argument("--date", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    session_dir = Path(cfg["session_dir"]).expanduser()
    session = Path(args.session) if args.session else _latest_session(session_dir)
    if not session or not session.exists():
        print("No session file found")
        return 0

    transcript = _load_session_text(session)
    ollama = OllamaService(
        host=cfg["ollama"]["host"],
        embedding_model=cfg["ollama"]["embedding_model"],
        generation_model=cfg["ollama"]["generation_model"],
    )
    summary = ollama.generate(
        "Extract memory flush notes from this session. Return markdown with bullets under headings: Facts, Decisions, Preferences, Open Loops.\n\n"
        + transcript[:30000],
        temperature=0.0,
    )

    stamp = args.date or datetime.utcnow().strftime("%Y-%m-%d")
    target = Path(cfg["memory_dir"]).expanduser() / f"{stamp}.md"
    body = f"# Daily Memory {stamp}\n\n## Auto Extracted\n{summary.strip()}\n"
    if args.dry_run and not args.apply:
        print(f"Dry run: would write {target}")
        return 0

    write_text(target, body)
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
