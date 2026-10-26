"""Optional dense embeddings served by a local Ollama instance.

Dense retrieval is strictly additive: if Ollama is not running, or the model is
not pulled, the retriever silently falls back to BM25 and the app keeps working.
"""

from __future__ import annotations

import math

import httpx


class EmbeddingUnavailable(RuntimeError):
    """Raised when the embedding backend cannot be reached."""


class OllamaEmbedder:
    backend = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=min(self.timeout, 3.0))
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:  # pragma: no cover - network dependent
            raise EmbeddingUnavailable(str(exc)) from exc
        vectors = payload.get("embeddings") or []
        if len(vectors) != len(texts):
            raise EmbeddingUnavailable("embedding count mismatch")
        return [[float(x) for x in vector] for vector in vectors]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
