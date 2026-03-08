# Second Brain Skill (Local)

Use this skill to manage OpenClaw memory locally with Ollama + FAISS.

## Requirements
- Python 3
- Ollama running locally
- Models:
  - `llama3.2` (generation)
  - `nomic-embed-text` (embeddings)

## Install
```bash
./install.sh
```

## Workflow
1. High-frequency memory flushes go to daily/agent logs (`extract_v2.py`).
2. Build/update local semantic index (`index.py`).
3. Search via `search.py` and cite exact lines via `get.py`.
4. Consolidate to canonical `MEMORY.md` (`consolidate.py`).
5. Compact + archive `MEMORY.md` periodically (`memory_compact.py`).

## Commands
```bash
python3 scripts/search.py "query"
python3 scripts/get.py <file> <start> <end>
python3 scripts/consolidate.py --dry-run
python3 scripts/consolidate.py --apply
python3 scripts/memory_compact.py --dry-run
python3 scripts/memory_compact.py --apply
python3 scripts/pipeline.py --dry-run
python3 scripts/pipeline.py --apply
```
