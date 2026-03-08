#!/usr/bin/env python3
"""Local Ollama helpers for embeddings and generation."""

from __future__ import annotations

from typing import Iterable, List

try:
    from ollama import Client  # type: ignore
except Exception:  # pragma: no cover
    Client = None


class OllamaService:
    def __init__(self, host: str, embedding_model: str, generation_model: str) -> None:
        if Client is None:
            raise RuntimeError("Missing dependency: ollama Python package (run ./install.sh)")
        self.client = Client(host=host)
        self.embedding_model = embedding_model
        self.generation_model = generation_model

    def embed(self, texts: Iterable[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            response = self.client.embeddings(model=self.embedding_model, prompt=text)
            vectors.append(response["embedding"])
        return vectors

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        response = self.client.generate(
            model=self.generation_model,
            prompt=prompt,
            options={"temperature": temperature},
        )
        return response["response"].strip()

    def ensure_models(self) -> None:
        models = self.client.list().get("models", [])
        names = {m.get("name", "") for m in models}
        needed = [self.embedding_model, self.generation_model]
        for model in needed:
            if model in names:
                continue
            self.client.pull(model)
