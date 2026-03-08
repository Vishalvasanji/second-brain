#!/usr/bin/env python3
"""Generate a weekly local digest from markdown memory files."""

from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from utils.memory_io import gather_memory_files, load_config, read_text
from utils.ollama_client import OllamaService


def main() -> int:
    cfg = load_config()
    since = datetime.utcnow().date() - timedelta(days=7)
    files = []
    for e in gather_memory_files(cfg, scope="shared"):
        if e["kind"] != "daily":
            continue
        try:
            d = datetime.strptime(e["path"].stem, "%Y-%m-%d").date()
            if d >= since:
                files.append(e["path"])
        except ValueError:
            continue
    merged = "\n\n".join(read_text(p)[:7000] for p in sorted(files))
    ollama = OllamaService(cfg["ollama"]["host"], cfg["ollama"]["embedding_model"], cfg["ollama"]["generation_model"])
    print(ollama.generate("Create a concise weekly memory digest in markdown.\n\n" + merged, temperature=0.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
