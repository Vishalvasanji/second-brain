#!/usr/bin/env python3
"""Memory path/config helpers for local git-backed Second Brain."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def _tiny_yaml_parse(text: str) -> Dict[str, Any]:
    """Very small YAML subset parser used only when PyYAML is unavailable."""
    root: Dict[str, Any] = {}
    stack: List[tuple[int, Dict[str, Any] | List[Any]]] = [(0, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()
        container = stack[-1][1]
        if line.startswith("- "):
            if isinstance(container, list):
                container.append(line[2:].strip().strip('"'))
            continue
        if ":" not in line or not isinstance(container, dict):
            continue
        key, value = [x.strip() for x in line.split(":", 1)]
        if value == "":
            # next indented lines define map or list
            nxt: Dict[str, Any] = {}
            container[key] = nxt
            stack.append((indent + 2, nxt))
        else:
            low = value.lower()
            if low in {"true", "false"}:
                v: Any = low == "true"
            else:
                try:
                    v = int(value)
                except ValueError:
                    try:
                        v = float(value)
                    except ValueError:
                        v = value.strip('"')
            container[key] = v

        # convert empty dict containers to list if first child starts with '- '
        if isinstance(container, dict) and key in container and isinstance(container[key], dict):
            maybe_list = container[key]
            if maybe_list == {} and any(l.startswith(" " * (indent + 2) + "- ") for l in text.splitlines()):
                container[key] = []
                stack[-1] = (stack[-1][0], container)
                stack.append((indent + 2, container[key]))
    return root


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    text = Path(config_path).read_text(encoding="utf-8")
    if yaml:
        cfg = yaml.safe_load(text) or {}
    else:
        cfg = _tiny_yaml_parse(text)

    for k in ["memory_dir", "session_dir", "memory_md"]:
        if isinstance(cfg.get(k), str):
            cfg[k] = str(Path(cfg[k]).expanduser())

    index_cfg = cfg.setdefault("index", {})
    index_dir = Path(index_cfg.get("dir", ".index"))
    index_cfg["dir"] = str(index_dir)
    index_cfg.setdefault("faiss_path", str(index_dir / "vectors.faiss"))
    index_cfg.setdefault("sqlite_path", str(index_dir / "chunks.sqlite"))
    index_cfg.setdefault("manifest_path", str(index_dir / "manifest.json"))
    index_cfg.setdefault("graph_path", str(index_dir / "graph.sqlite"))

    cfg.setdefault("ollama", {})
    cfg["ollama"].setdefault("host", "http://localhost:11434")
    cfg["ollama"].setdefault("embedding_model", "nomic-embed-text")
    cfg["ollama"].setdefault("generation_model", "llama3.2")

    cfg.setdefault("memory", {})
    cfg["memory"].setdefault("daily_globs", ["*.md", "daily/*.md"])
    cfg["memory"].setdefault("archives_dir", "archives")
    cfg["memory"].setdefault("agents_dir", "agents")
    cfg["memory"].setdefault("handbook_dir", "handbook")
    cfg["memory"].setdefault("lessons_file", "lessons-learned.md")

    cfg.setdefault("search", {})
    cfg["search"].setdefault("max_results", 10)
    cfg["search"].setdefault("ranking_weights", {
        "similarity": 0.68,
        "authority": 0.18,
        "recency": 0.10,
        "scope": 0.08,
        "archive_penalty": 0.04,
    })

    cfg.setdefault("compaction", {})
    cfg["compaction"].setdefault("enabled", True)
    cfg["compaction"].setdefault("max_memory_md_bytes", 240000)
    cfg["compaction"].setdefault("max_memory_md_tokens", 50000)
    cfg["compaction"].setdefault("weekly_schedule_enabled", True)
    cfg["compaction"].setdefault("weekly_day", "sunday")
    cfg["compaction"].setdefault("compaction_version", "v1")

    return cfg


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _collect_glob(base: Path, patterns: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for pattern in patterns:
        out.extend(base.glob(pattern))
    return out


def gather_memory_files(
    config: Dict[str, Any],
    scope: str = "shared",
    agent: Optional[str] = None,
    date_range: Optional[Tuple[date, date]] = None,
) -> List[Dict[str, Any]]:
    memory_dir = Path(config["memory_dir"]).expanduser()
    memory_md = Path(config["memory_md"]).expanduser()
    mem_cfg = config["memory"]

    files: List[Tuple[Path, str, Optional[str], str]] = []

    if memory_md.exists():
        files.append((memory_md, "shared", None, "memory_md"))

    lessons = memory_dir / mem_cfg["lessons_file"]
    if lessons.exists():
        files.append((lessons, "shared", None, "lessons"))

    handbook_dir = memory_dir / mem_cfg["handbook_dir"]
    if handbook_dir.exists():
        for p in handbook_dir.rglob("*.md"):
            files.append((p, "shared", None, "handbook"))

    archives_dir = memory_dir / mem_cfg["archives_dir"]
    if archives_dir.exists():
        for p in archives_dir.rglob("*.md"):
            files.append((p, "shared", None, "archive"))

    for p in _collect_glob(memory_dir, mem_cfg["daily_globs"]):
        if p.is_file() and p.suffix == ".md" and p.name != lessons.name and "archives" not in p.parts and "handbook" not in p.parts and "agents" not in p.parts:
            files.append((p, "shared", None, "daily"))

    agents_root = memory_dir / mem_cfg["agents_dir"]
    if scope == "all" and agents_root.exists():
        for p in agents_root.rglob("*.md"):
            if len(p.relative_to(agents_root).parts) > 1:
                files.append((p, "agent", p.relative_to(agents_root).parts[0], "agent"))
    elif scope.startswith("agent:") and agents_root.exists():
        name = scope.split(":", 1)[1]
        for p in (agents_root / name).rglob("*.md"):
            files.append((p, "agent", name, "agent"))
    elif scope == "agent" and agent and agents_root.exists():
        for p in (agents_root / agent).rglob("*.md"):
            files.append((p, "agent", agent, "agent"))

    seen = set()
    results = []
    for path, vis, ag, kind in files:
        if not path.exists():
            continue
        if path in seen:
            continue
        seen.add(path)
        if date_range and kind == "daily":
            try:
                d = datetime.strptime(path.stem, "%Y-%m-%d").date()
                if not (date_range[0] <= d <= date_range[1]):
                    continue
            except ValueError:
                pass
        results.append({"path": path, "visibility": vis, "agent": ag, "kind": kind})

    return sorted(results, key=lambda x: str(x["path"]))


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


# Backward-compatible helpers
def get_memory_files(memory_dir: Path, date_range=None):
    cfg = load_config()
    cfg["memory_dir"] = str(Path(memory_dir))
    return [e["path"] for e in gather_memory_files(cfg, scope="shared", date_range=date_range)]

def read_memory_file(file_path: Path):
    text = read_text(Path(file_path)) if Path(file_path).exists() else ""
    st = Path(file_path).stat() if Path(file_path).exists() else None
    return {"path": str(file_path), "content": text, "sections": {}, "size": (st.st_size if st else 0), "modified": datetime.fromtimestamp(st.st_mtime) if st else None, "created": datetime.fromtimestamp(st.st_ctime) if st else None}

def write_memory_file(file_path: Path, content: str, backup: bool = True):
    fp = Path(file_path)
    if backup and fp.exists():
        fp.with_suffix(fp.suffix+".bak").write_text(fp.read_text(encoding="utf-8"), encoding="utf-8")
    write_text(fp, content)

def load_memory_index(memory_dir: Path):
    return load_json(Path(memory_dir)/".memory-index.json", {"memories": {}, "last_updated": None, "version": "1.0"})

def save_memory_index(memory_dir: Path, index):
    save_json(Path(memory_dir)/".memory-index.json", index)

def append_pipeline_log(memory_dir: Path, entry):
    p = Path(memory_dir)/".pipeline-log.json"
    log = load_json(p, [])
    entry["timestamp"] = datetime.utcnow().isoformat()+"Z"
    log.append(entry)
    save_json(p, log[-100:])

def load_pipeline_log(memory_dir: Path):
    return load_json(Path(memory_dir)/".pipeline-log.json", [])

def save_pipeline_log(memory_dir: Path, log_entries):
    save_json(Path(memory_dir)/".pipeline-log.json", log_entries)
