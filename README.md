# Second Brain (Local Theo Memory Engine)

This fork runs fully local on a single machine using **Ollama + FAISS + SQLite**.

## What stays canonical
- `~/.openclaw/workspace/MEMORY.md` remains the canonical long-term memory file (still injected by OpenClaw).
- Daily flushes should land in daily/agent logs first; consolidation/compaction updates `MEMORY.md` in separate jobs.

## What is indexed for semantic retrieval
- `MEMORY.md`
- `memory/*.md` and/or `memory/daily/*.md`
- `memory/handbook/**`
- `memory/agents/**` (scope-aware)
- `memory/lessons-learned.md`
- `memory/archives/**` (critical)

## Install
```bash
./install.sh
```

## Core commands
```bash
python3 scripts/index.py --scope all
python3 scripts/search.py "query"
python3 scripts/get.py <file> <start_line> <end_line>
python3 scripts/consolidate.py --dry-run
python3 scripts/consolidate.py --apply
python3 scripts/memory_compact.py --dry-run
python3 scripts/memory_compact.py --apply
python3 scripts/pipeline.py --dry-run
python3 scripts/pipeline.py --apply
```

## Scopes
- `shared` (default)
- `agent:<name>` (agent private + shared)
- `all` (admin/debug)

`--agent` uses `OPENCLAW_AGENT` by default, but CLI value overrides env.

## Memory compaction behavior
Compaction is a deterministic rewrite with mandatory snapshotting:
- snapshot target: `memory/archives/memory-md-snapshots/YYYY-MM-DD-HHMM.md`
- YAML front matter includes:
  - `timestamp`
  - `pre_size_bytes`
  - `reason`
  - `sha256`
  - `compaction_version`

After rewrite, index is rebuilt/updated so archives remain searchable.

## Local derived indexes (ignored by git)
- `.index/vectors.faiss`
- `.index/chunks.sqlite`
- `.index/manifest.json`
- optional `.index/graph.sqlite`
