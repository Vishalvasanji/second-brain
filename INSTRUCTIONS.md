THEO MEMORY ENGINE
LOCAL SEMANTIC MEMORY SYSTEM FOR OPENCLAW

Purpose

This repository upgrades Theo’s memory architecture so that knowledge persists across sessions and across agents without increasing prompt token cost. The system keeps MEMORY.md as the canonical long-term memory file used by OpenClaw while allowing historical knowledge to grow indefinitely through indexed archives and semantic retrieval.

The system runs fully local on a single machine using:

Ollama
FAISS
SQLite
Git

No external vector databases or SaaS services are required.

The system provides:

persistent memory storage
semantic search across all memory
memory consolidation and compaction
cross-session knowledge retrieval
cross-agent knowledge sharing

SYSTEM COMPONENTS

Component 1 — Canonical Memory Files

These files are the authoritative source of truth and must remain tracked in Git.

Location
~/.openclaw/workspace/

Files

MEMORY.md
Canonical long-term memory file injected into the OpenClaw system prompt.

memory/daily/YYYY-MM-DD.md
Daily session memory logs.

memory/handbook/
Standard operating procedures and reference documentation.

memory/agents/<agent>/
Agent-specific memory storage.

memory/lessons-learned.md
Mistakes, debugging insights, and resolved issues.

memory/archives/
Archived snapshots of compacted memory.

Component 2 — Local Search Index

Location
~/.openclaw/workspace/.index/

Files

vectors.faiss
Vector embeddings for memory chunks.

chunks.sqlite
Metadata database storing file paths and line ranges.

manifest.json
Index metadata.

graph.sqlite (optional)
Entity relationship graph.

These files are derived artifacts and must never be committed to Git.

MEMORY SOURCES INDEXED FOR SEARCH

Semantic search must include all canonical memory sources:

MEMORY.md
memory/daily
memory/handbook
memory/agents
memory/lessons-learned.md
memory/archives

Archived memory must remain searchable indefinitely.

WHY THIS SYSTEM EXISTS

Without memory lifecycle management, MEMORY.md grows indefinitely because OpenClaw injects it into every prompt.

This leads to:

increasing token costs
reduced context window for reasoning
context compaction pressure
lower reasoning quality

This system solves that problem through:

semantic retrieval
memory consolidation
memory compaction
archival of historical knowledge

INSTALLATION PROCEDURE

Phase 1 — Install Dependencies

Theo must install required Python dependencies.

pip install faiss-cpu numpy pyyaml sqlite-utils ollama

Indexing and search will fail if faiss-cpu or numpy are missing.

Phase 2 — Verify Ollama Models

Check installed models.

ollama list

Required models:

llama3.2
nomic-embed-text

If missing:

ollama pull llama3.2
ollama pull nomic-embed-text

Phase 3 — Verify OpenClaw Workspace Paths

Ensure the following paths exist.

~/.openclaw/workspace/MEMORY.md
~/.openclaw/workspace/memory/

Create directories if missing.

Phase 4 — Create Index Directory

mkdir -p ~/.openclaw/workspace/.index

INITIALIZATION

Phase 5 — Build Initial Memory Index

Run the index builder.

python3 scripts/index.py --scope all

This must produce:

vectors.faiss
chunks.sqlite

Search will not work until indexing completes successfully.

CORE COMMANDS

Index Memory

python3 scripts/index.py --scope all

Search Memory

python3 scripts/search.py "query"

Retrieve Exact Memory Lines

python3 scripts/get.py file start_line end_line

Preview Consolidation

python3 scripts/consolidate.py --dry-run

Apply Consolidation

python3 scripts/consolidate.py --apply

Preview Memory Compaction

python3 scripts/memory_compact.py --dry-run

Apply Memory Compaction

python3 scripts/memory_compact.py --apply

Run Full Pipeline

python3 scripts/pipeline.py --apply

SEARCH SCOPES

shared
shared memory only

agent:<name>
agent-private plus shared memory

all
administrator scope

MEMORY RETRIEVAL RULE

If asked about past work, configuration, decisions, or historical information:

Theo must perform the following steps.

1 run semantic search
2 retrieve the referenced lines
3 answer using retrieved memory
4 never guess historical information

MEMORY PROCESSING SCHEDULE

Theo must process memory across three operational time horizons: session, daily, and weekly. This schedule governs how knowledge flows from raw session activity into structured long-term memory.

SESSION LEVEL MEMORY

During an active session:

1. New decisions, observations, and operational context are captured in session activity.
2. Memory flush writes durable entries to:

memory/daily/YYYY-MM-DD.md

3. MEMORY.md must never be modified during a live session.

Session logs are raw memory and may contain redundant or temporary information.

DAILY MEMORY PROCESSING

Once per day Theo must run the memory pipeline.

Purpose:

convert raw daily memory into structured searchable memory.

Daily pipeline tasks:

extract important information from daily logs
score memories by importance
update semantic search index
generate memory health statistics

Example command:

python3 scripts/pipeline.py --apply

The daily pipeline should not automatically modify MEMORY.md unless consolidation is explicitly enabled.

WEEKLY MEMORY CONSOLIDATION

Once per week Theo should consolidate daily memories.

Purpose:

promote important information into canonical long-term memory.

Weekly consolidation tasks:

review the previous week of daily logs
identify important decisions and system changes
merge relevant information into MEMORY.md
remove duplicate entries
categorize new knowledge

Example command:

python3 scripts/consolidate.py --apply

WEEKLY MEMORY COMPACTION

After consolidation Theo must evaluate MEMORY.md size.

If thresholds are exceeded:

1 snapshot MEMORY.md to the archive directory
2 rewrite MEMORY.md removing redundant history
3 rebuild the semantic search index

Example command:

python3 scripts/memory_compact.py --apply

COMPACTION ARCHIVE RULES

Before MEMORY.md is rewritten, a snapshot must be created.

Archive location:

memory/archives/memory-md-snapshots/

Filename format:

YYYY-MM-DD-HHMM.md

Snapshot metadata must include:

timestamp
pre_size_bytes
reason
sha256 checksum
compaction_version

All archived snapshots must remain indexed so semantic search can retrieve them.

OPENCLAW MEMORY FLUSH

During active sessions memory flush writes session notes to:

memory/daily/YYYY-MM-DD.md

Flush must never write directly to MEMORY.md.

Updates to MEMORY.md occur only through consolidation or compaction jobs.

MULTI AGENT MEMORY MODEL

Shared Memory

MEMORY.md
handbook
daily logs
archives
lessons learned

Agent Private Memory

memory/agents/<agent>

Default search behavior:

agents search shared memory and their own private memory.

Access to other agents’ private memory requires explicit scope.

AUTOMATED MEMORY PIPELINE

A nightly pipeline may perform:

memory extraction
memory scoring
semantic index updates
optional consolidation
memory health reporting

Example:

python3 scripts/pipeline.py --apply

MEMORY HEALTH MONITORING

Memory statistics can be inspected using:

python3 scripts/stats.py

Statistics include:

memory growth rate
category distribution
pipeline health
consolidation coverage

ENTITY RELATIONSHIP GRAPH

The system may optionally build an entity graph connecting:

projects
technologies
people
decisions

Build graph:

python3 scripts/graph.py --build

Query graph:

python3 scripts/graph.py --query "topic"

SYSTEM VALIDATION

The system is operational only if all validation checks pass.

Dependencies installed successfully
Ollama models present
Workspace memory directories exist
Index build completes successfully
Semantic search returns results
Memory compaction produces archive snapshots
Archived memory remains searchable

FAILURE CONDITIONS

The system is considered non-operational if:

FAISS index missing
SQLite metadata missing
Ollama models missing
index build fails
semantic search returns no results for known memory

INSTRUCTIONS FOR THEO

If you are Theo reading this file you must perform the following sequence.

Step 1
install dependencies

Step 2
verify Ollama models

Step 3
verify memory directories

Step 4
build semantic index

Step 5
test semantic search

Step 6
test consolidation

Step 7
test memory compaction and archive creation

Step 8
confirm archived memory is searchable

Step 9
enforce the memory retrieval rule in conversations

Step 10
report system status

Do not assume success. Every step must be verified before continuing.

End of file.

