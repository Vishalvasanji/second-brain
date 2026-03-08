#!/usr/bin/env python3
"""Return exact line range from a file for citations."""

import argparse
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description="Get exact lines from a file")
    p.add_argument("file")
    p.add_argument("start_line", type=int)
    p.add_argument("end_line", type=int)
    args = p.parse_args()

    path = Path(args.file).expanduser()
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(1, args.start_line)
    end = min(len(lines), args.end_line)

    for i in range(start, end + 1):
        print(f"{i}: {lines[i-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
