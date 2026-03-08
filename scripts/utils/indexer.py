#!/usr/bin/env python3
"""FAISS + SQLite markdown indexer using Ollama embeddings."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    import faiss  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    faiss = None
    np = None

from .memory_io import gather_memory_files, load_json, read_text, save_json
from .ollama_client import OllamaService


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _chunk_markdown(text: str, target_tokens: int = 450, min_tokens: int = 280) -> List[Dict[str, Any]]:
    lines = text.splitlines()
    chunks: List[Dict[str, Any]] = []
    cur: List[str] = []
    start = 1

    def flush(end_line: int) -> None:
        nonlocal cur, start
        content = "\n".join(cur).strip()
        if content:
            chunks.append({"text": content, "start_line": start, "end_line": end_line})
        cur = []

    for i, line in enumerate(lines, start=1):
        token_est = len(" ".join(cur + [line])) // 4
        is_heading = line.startswith("#")
        if cur and ((is_heading and token_est >= min_tokens) or token_est >= target_tokens):
            flush(i - 1)
            start = i
        cur.append(line)
    if cur:
        flush(len(lines))
    return chunks


def _open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            embedding_id INTEGER UNIQUE,
            file_path TEXT,
            start_line INTEGER,
            end_line INTEGER,
            content TEXT,
            file_type TEXT,
            visibility TEXT,
            agent TEXT,
            is_archive INTEGER,
            mtime REAL,
            authority REAL,
            file_hash TEXT
        )
        """
    )
    conn.commit()
    return conn


def _load_or_create_index(path: Path, dim: int) -> faiss.IndexIDMap2:
    if path.exists():
        idx = faiss.read_index(str(path))
        if isinstance(idx, faiss.IndexIDMap2):
            return idx
        return faiss.IndexIDMap2(idx)
    return faiss.IndexIDMap2(faiss.IndexFlatIP(dim))


def _authority(file_type: str) -> float:
    return {
        "memory_md": 1.0,
        "handbook": 0.95,
        "lessons": 0.92,
        "agent": 0.85,
        "daily": 0.7,
        "archive": 0.6,
    }.get(file_type, 0.75)


def build_or_update_index(config: Dict[str, Any], scope: str = "shared", agent: str | None = None) -> Dict[str, Any]:
    if faiss is None or np is None:
        raise RuntimeError("Missing dependencies: install faiss-cpu and numpy (run ./install.sh)")
    idx_cfg = config["index"]
    manifest_path = Path(idx_cfg["manifest_path"])
    sqlite_path = Path(idx_cfg["sqlite_path"])
    faiss_path = Path(idx_cfg["faiss_path"])

    file_entries = gather_memory_files(config, scope=scope, agent=agent)
    manifest = load_json(manifest_path, {"files": {}, "updated_at": None})
    old_files: Dict[str, str] = manifest.get("files", {})

    current_files = {str(e["path"]): _hash_file(e["path"]) for e in file_entries}
    changed = [p for p, h in current_files.items() if old_files.get(p) != h]
    removed = [p for p in old_files if p not in current_files]

    ollama = OllamaService(
        host=config["ollama"]["host"],
        embedding_model=config["ollama"]["embedding_model"],
        generation_model=config["ollama"]["generation_model"],
    )

    conn = _open_db(sqlite_path)
    cur = conn.cursor()

    dim = None
    if faiss_path.exists():
        idx = _load_or_create_index(faiss_path, 768)
        dim = idx.d
    else:
        probe = ollama.embed(["embedding-dimension-probe"])[0]
        dim = len(probe)
        idx = _load_or_create_index(faiss_path, dim)

    def remove_file(file_path: str) -> None:
        rows = cur.execute("SELECT embedding_id FROM chunks WHERE file_path=?", (file_path,)).fetchall()
        if rows:
            ids = np.array([r[0] for r in rows], dtype=np.int64)
            idx.remove_ids(ids)
        cur.execute("DELETE FROM chunks WHERE file_path=?", (file_path,))

    for p in removed + changed:
        remove_file(p)

    max_id = cur.execute("SELECT COALESCE(MAX(embedding_id), 0) FROM chunks").fetchone()[0]
    next_id = int(max_id) + 1

    for e in file_entries:
        fp = str(e["path"])
        if fp not in changed:
            continue
        text = read_text(e["path"])
        chunks = _chunk_markdown(text)
        if not chunks:
            continue
        vectors = ollama.embed([c["text"] for c in chunks])
        vec_np = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(vec_np)
        ids = np.arange(next_id, next_id + len(chunks), dtype=np.int64)
        idx.add_with_ids(vec_np, ids)

        for i, ch in enumerate(chunks):
            chunk_id = f"{fp}:{ch['start_line']}-{ch['end_line']}"
            cur.execute(
                """INSERT INTO chunks(chunk_id, embedding_id, file_path, start_line, end_line, content, file_type, visibility, agent, is_archive, mtime, authority, file_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk_id,
                    int(ids[i]),
                    fp,
                    ch["start_line"],
                    ch["end_line"],
                    ch["text"],
                    e["kind"],
                    e["visibility"],
                    e["agent"],
                    1 if e["kind"] == "archive" else 0,
                    Path(fp).stat().st_mtime,
                    _authority(e["kind"]),
                    current_files[fp],
                ),
            )
        next_id += len(chunks)

    conn.commit()
    faiss_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(idx, str(faiss_path))

    save_json(manifest_path, {"files": current_files, "updated_at": datetime.utcnow().isoformat() + "Z"})
    total = cur.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()

    return {
        "indexed_files": len(file_entries),
        "changed_files": len(changed),
        "removed_files": len(removed),
        "total_chunks": int(total),
        "faiss_path": str(faiss_path),
        "sqlite_path": str(sqlite_path),
    }


def search_index(config: Dict[str, Any], query: str, limit: int, scope: str = "shared", agent: str | None = None) -> List[Dict[str, Any]]:
    if faiss is None or np is None:
        raise RuntimeError("Missing dependencies: install faiss-cpu and numpy (run ./install.sh)")
    idx_cfg = config["index"]
    faiss_path = Path(idx_cfg["faiss_path"])
    sqlite_path = Path(idx_cfg["sqlite_path"])
    if not faiss_path.exists() or not sqlite_path.exists():
        return []

    ollama = OllamaService(
        host=config["ollama"]["host"],
        embedding_model=config["ollama"]["embedding_model"],
        generation_model=config["ollama"]["generation_model"],
    )

    idx = faiss.read_index(str(faiss_path))
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    qv = np.array([ollama.embed([query])[0]], dtype=np.float32)
    faiss.normalize_L2(qv)
    scores, ids = idx.search(qv, max(limit * 8, 30))

    now = datetime.utcnow().timestamp()
    weights = config.get("search", {}).get("ranking_weights", {})

    out = []
    for sim, emb_id in zip(scores[0], ids[0]):
        if emb_id < 0:
            continue
        row = conn.execute("SELECT * FROM chunks WHERE embedding_id=?", (int(emb_id),)).fetchone()
        if not row:
            continue
        if scope == "shared" and row["visibility"] != "shared":
            continue
        if scope.startswith("agent:"):
            name = scope.split(":", 1)[1]
            if not (row["visibility"] == "shared" or row["agent"] == name):
                continue

        recency = 1.0 / (1.0 + ((now - float(row["mtime"])) / 86400.0) / 30.0)
        scope_bonus = 1.0
        if scope.startswith("agent:") and row["agent"] == scope.split(":", 1)[1]:
            scope_bonus = 1.12
        archive_penalty = 0.25 if row["is_archive"] else 0.0

        final = (
            float(sim) * weights.get("similarity", 0.68)
            + float(row["authority"]) * weights.get("authority", 0.18)
            + recency * weights.get("recency", 0.1)
            + scope_bonus * weights.get("scope", 0.08)
            - archive_penalty * weights.get("archive_penalty", 0.04)
        )
        out.append(
            {
                "file_path": row["file_path"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "score": round(final, 6),
                "similarity": round(float(sim), 6),
                "snippet": row["content"][:350],
                "file_type": row["file_type"],
            }
        )

    conn.close()
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]
