#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
python3 -m pip install faiss-cpu numpy pyyaml sqlite-utils ollama rank-bm25

mkdir -p .index

if command -v ollama >/dev/null 2>&1; then
  ollama list | grep -q "llama3.2" || ollama pull llama3.2
  ollama list | grep -q "nomic-embed-text" || ollama pull nomic-embed-text
else
  echo "ollama CLI not found; install Ollama first" >&2
fi

echo "Install complete."
