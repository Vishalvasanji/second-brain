THEO MEMORY ENGINE
LOCAL SEMANTIC MEMORY SYSTEM FOR OPENCLAW

PURPOSE

This repository upgrades Theo’s memory architecture so that knowledge persists across sessions and across agents without increasing prompt token cost.

The system keeps MEMORY.md as the canonical memory file used by OpenClaw while moving historical information into indexed searchable storage.

The architecture runs fully local using:

Ollama
FAISS
SQLite
Git

No cloud vector databases are used.

The system provides:

persistent memory storage
semantic search across all memory
memory compaction and archival
cross-session knowledge retrieval
cross-agent knowledge sharing

---

SYSTEM COMPONENTS

COMPONENT 1
CANONICAL MEMORY FILES

These files are the source of truth and must remain in Git.

Location

~/.openclaw/workspace/

Files

MEMORY.md
canonical long-term memory

memory/daily/YYYY-MM-DD.md
session memory logs

memory/handbook/
SOPs and reference documentation

memory/agents/<agent>/
agent-specific memory

memory/lessons-learned.md
mistakes and debugging insights

memory/archives/
snapshots of compacted memory

COMPONENT 2
LOCAL SEARCH INDEX

Location

~/.openclaw/workspace/.index/

Files

vectors.faiss
vector embeddings for memory chunks

chunks.sqlite
metadata for file paths and line ranges

manifest.json
index metadata

graph.sqlite (optional)
entity relationship graph

These files are derived artifacts and must never be committed to Git.

---

MEMORY SOURCES INDEXED FOR SEARCH

Semantic search must include all canonical memory.

Sources

MEMORY.md
memory/daily files
memory/handbook
memory/agents
memory/lessons-learned.md
memory/archives

Archived memory must remain searchable indefinitely.

---

WHY THIS SYSTEM EXISTS

Without memory management, MEMORY.md grows continuously.

Because OpenClaw injects MEMORY.md into every prompt, growth causes:

increasing token costs
reduced context window
context compaction pressure
lower reasoning quality

This system solves the problem using:

memory compaction
memory archival
semantic retrieval

---

INSTALLATION PROCEDURE

PHASE 1
INSTALL DEPENDENCIES

Theo must install required Python packages.

pip install faiss-cpu numpy pyyaml sqlite-utils ollama

Indexing and search will fail if faiss-cpu or numpy are missing.

PHASE 2
VERIFY OLLAMA MODELS

Check installed models.

ollama list

Required models

llama3.2
nomic-embed-text

If missing, install them.

ollama pull llama3.2
ollama pull nomic-embed-text

PHASE 3
VERIFY OPENCLAW MEMORY PATHS

Ensure the following directories exist.

~/.openclaw/workspace/MEMORY.md
~/.openclaw/workspace/memory/

Create directories if missing.

PHASE 4
CREATE INDEX DIRECTORY

mkdir -p ~/.openclaw/workspace/.index

---

INITIALIZATION

PHASE 5
BUILD INITIAL MEMORY INDEX

Run the index builder.

python3 scripts/index.py --scope all

The index must read all canonical memory files and produce:

vectors.faiss
chunks.sqlite

Search will not work until indexing completes successfully.

---

CORE COMMANDS

INDEX MEMORY

python3 scripts/index.py --scope all

SEARCH MEMORY

python3 scripts/search.py "query"

RETRIEVE EXACT MEMORY LINES

python3 scripts/get.py file start_line end_line

PREVIEW CONSOLIDATION

python3 scripts/consolidate.py --dry-run

APPLY CONSOLIDATION

python3 scripts/consolidate.py --apply

PREVIEW MEMORY COMPACTION

python3 scripts/memory_compact.py --dry-run

APPLY MEMORY COMPACTION

python3 scripts/memory_compact.py --apply

RUN AUTOMATED PIPELINE

python3 scripts/pipeline.py --apply

---

SEARCH SCOPES

shared
shared memory only

agent:<name>
agent private plus shared memory

all
administrator scope

---

MEMORY RETRIEVAL RULE

If asked about past decisions, configuration, or historical context:

Theo must perform the following steps.

1 run semantic search
2 retrieve the referenced lines
3 answer using retrieved memory
4 never guess historical information

---

MEMORY CONSOLIDATION

Daily logs accumulate in memory/daily.

Consolidation distills important information from daily logs into MEMORY.md.

Consolidation performs:

deduplication
categorization
importance ranking
memory updates

---

MEMORY COMPACTION

PROBLEM

MEMORY.md cannot grow indefinitely.

TRIGGERS

Compaction occurs when one of the following occurs:

size threshold exceeded
token estimate exceeded
weekly scheduled compaction

COMPACTION PROCESS

Step 1

Snapshot MEMORY.md before modification.

Archive location

memory/archives/memory-md-snapshots/

Snapshot filename format

YYYY-MM-DD-HHMM.md

Snapshot metadata must include

timestamp
pre_size_bytes
reason
sha256 checksum
compaction_version

Step 2

Rewrite MEMORY.md to remove redundant history while preserving key decisions.

Step 3

Rebuild the semantic search index.

---

OPENCLAW MEMORY FLUSH

During active sessions memory flush writes session notes to

memory/daily/YYYY-MM-DD.md

Flush must never write directly to MEMORY.md.

Updates to MEMORY.md occur through consolidation or compaction jobs.

---

MULTI AGENT MEMORY MODEL

SHARED MEMORY

MEMORY.md
handbook
daily logs
archives
lessons learned

AGENT PRIVATE MEMORY

memory/agents/<agent>

Default search behavior

agents search shared memory and their private memory

access to other agents requires explicit scope.

---

AUTOMATED MEMORY PIPELINE

A nightly pipeline may perform the following tasks.

extract session memories
score memory relevance
update semantic index
optionally consolidate memory
generate memory health report

Example

python3 scripts/pipeline.py --apply

---

MEMORY HEALTH MONITORING

Memory statistics can be inspected using

python3 scripts/stats.py

Statistics include

memory growth rate
category distribution
pipeline health
consolidation coverage

---

ENTITY RELATIONSHIP GRAPH

The system may optionally construct an entity graph linking

projects
people
technologies
decisions

Build graph

python3 scripts/graph.py --build

Query graph

python3 scripts/graph.py --query "topic"

---

SYSTEM VALIDATION

The system is operational only if all validation checks pass.

Validation steps

dependencies installed successfully
ollama models present
workspace memory directories exist
index build completes
semantic search returns results
memory compaction produces archive
archived memory is searchable

---

FAILURE CONDITIONS

The system is considered non operational if

FAISS index missing
SQLite metadata missing
Ollama models missing
index build fails
search returns no results for known memory

---

INSTRUCTIONS FOR THEO

If you are Theo reading this file you must execute the following sequence.

STEP 1
install dependencies

STEP 2
verify ollama models

STEP 3
verify memory directories

STEP 4
build semantic index

STEP 5
test semantic search

STEP 6
test memory compaction

STEP 7
enforce retrieval rule in conversations

STEP 8
report system status

Do not assume success.
Every step must be verified before continuing.

---

END OF FILE
