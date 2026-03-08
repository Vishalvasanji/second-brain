#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))
from utils.memory_io import load_config
from utils.indexer import build_or_update_index


def main() -> int:
    p = argparse.ArgumentParser(description="Build local FAISS+SQLite memory index")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--scope", default="shared", choices=["shared", "all"])
    p.add_argument("--agent", default=None)
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    try:
        res = build_or_update_index(cfg, scope=args.scope, agent=args.agent)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
