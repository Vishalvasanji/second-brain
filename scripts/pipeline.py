#!/usr/bin/env python3
"""Local nightly pipeline: extract(optional) -> score -> index -> consolidate(optional) -> stats."""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.memory_io import load_config


def run_step(cmd, dry_run: bool):
    print(f"[pipeline] {'DRY-RUN ' if dry_run else ''}{' '.join(cmd)}")
    if dry_run:
        return 0
    return subprocess.call(cmd)


def main() -> int:
    p = argparse.ArgumentParser(description="Run local second-brain pipeline")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    dry = args.dry_run and not args.apply

    steps = []
    pipe_cfg = cfg.get("pipeline", {})
    py = sys.executable

    if pipe_cfg.get("extract_recent", False):
        steps.append([py, "scripts/extract_v2.py", "--config", args.config])
    if pipe_cfg.get("update_scores", True):
        steps.append([py, "scripts/score.py", "--config", args.config, "--reindex"])
    steps.append([py, "scripts/index.py", "--config", args.config, "--scope", "all"])
    if pipe_cfg.get("consolidate", False):
        steps.append([py, "scripts/consolidate.py", "--config", args.config] + (["--dry-run"] if dry else ["--apply"]))
    if pipe_cfg.get("generate_report", True):
        steps.append([py, "scripts/stats.py", "--config", args.config])

    rc = 0
    for step in steps:
        code = run_step(step, dry)
        if code != 0:
            rc = code
            print(f"[pipeline] failed: {' '.join(step)}")
            break

    print("[pipeline] done")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
