#!/usr/bin/env python3
"""Snapshot + deterministic rewrite compaction for MEMORY.md."""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from utils.indexer import build_or_update_index
from utils.memory_io import estimate_tokens, load_config, read_text, write_text
from utils.ollama_client import OllamaService


def snapshot_memory(memory_md: Path, archives_root: Path, reason: str, version: str) -> Path:
    original = read_text(memory_md)
    timestamp = datetime.utcnow()
    archive = archives_root / "memory-md-snapshots" / f"{timestamp.strftime('%Y-%m-%d-%H%M')}.md"
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    front_matter = (
        f"---\n"
        f"timestamp: {timestamp.isoformat()}Z\n"
        f"pre_size_bytes: {len(original.encode('utf-8'))}\n"
        f"reason: {reason}\n"
        f"sha256: {digest}\n"
        f"compaction_version: {version}\n"
        f"---\n\n"
    )
    write_text(archive, front_matter + original)
    return archive


def _local_dedupe(content: str) -> str:
    seen = set()
    out = []
    for line in content.splitlines():
        k = line.strip().lower()
        if k and (k.startswith("- ") or k.startswith("*") or len(k) > 30):
            if k in seen:
                continue
            seen.add(k)
        out.append(line)
    return "\n".join(out).strip() + "\n"


def rewrite_memory(content: str, ollama: OllamaService) -> str:
    prompt = (
        "Rewrite this MEMORY.md deterministically. Keep factual content, remove duplicates, compress stale narrative, "
        "preserve important decisions/preferences/todos. Output valid markdown only with sections: "
        "## Active Context, ## Stable Facts, ## Decisions, ## Preferences, ## Open Threads, ## Historical Notes.\n\n"
        "MEMORY.md:\n"
        f"{content[:120000]}"
    )
    try:
        out = ollama.generate(prompt, temperature=0.0)
        return out.strip() + "\n"
    except Exception:
        return _local_dedupe(content)


def main() -> int:
    p = argparse.ArgumentParser(description="Compact MEMORY.md with mandatory snapshot")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--reason", default="manual_compaction")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    memory_md = Path(cfg["memory_md"]).expanduser()
    memory_dir = Path(cfg["memory_dir"]).expanduser()
    archives_root = memory_dir / cfg["memory"]["archives_dir"]
    version = cfg["compaction"].get("compaction_version", "v1")

    if not memory_md.exists():
        print(f"Missing MEMORY.md: {memory_md}")
        return 1

    content = read_text(memory_md)
    ollama = OllamaService(
        host=cfg["ollama"]["host"],
        embedding_model=cfg["ollama"]["embedding_model"],
        generation_model=cfg["ollama"]["generation_model"],
    )
    rewritten = rewrite_memory(content, ollama)

    if args.dry_run and not args.apply:
        print(f"Dry run: would snapshot and rewrite {memory_md}")
        print(f"Before bytes={len(content.encode())} tokens~{estimate_tokens(content)}")
        print(f"After  bytes={len(rewritten.encode())} tokens~{estimate_tokens(rewritten)}")
        return 0

    archive = snapshot_memory(memory_md, archives_root, args.reason, version)
    write_text(memory_md, rewritten)
    try:
        idx = build_or_update_index(cfg, scope="all")
    except RuntimeError as e:
        idx = {"warning": str(e)}
    print(f"Snapshot: {archive}")
    print(f"Reindex: {idx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
