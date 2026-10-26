"""Hybrid retrieval: BM25 always on, dense cosine when vectors exist."""

from __future__ import annotations

from typing import Protocol

from symptompilot.models import Passage, SourceRef
from symptompilot.retrieval.bm25 import BM25Index, tokenize
from symptompilot.retrieval.embedder import cosine
from symptompilot.retrieval.expansion import concept_groups, flatten
from symptompilot.retrieval.store import ChunkRecord, KnowledgeStore


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HybridRetriever:
    """Ranks chunks by a weighted blend of lexical and (optional) dense scores."""

    def __init__(
        self,
        store: KnowledgeStore,
        embedder: Embedder | None = None,
        bm25_weight: float = 0.65,
        min_score: float = 0.05,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.bm25_weight = min(1.0, max(0.0, bm25_weight))
        self.min_score = min_score
        self.chunks: list[ChunkRecord] = []
        self.vectors: dict[str, list[float]] = {}
        self._index: BM25Index | None = None

    # ------------------------------------------------------------------ index
    @property
    def dense_enabled(self) -> bool:
        return bool(self.embedder and self.vectors)

    def refresh(self) -> HybridRetriever:
        self.chunks = self.store.load_chunks()
        documents = [
            tokenize(f"{chunk.title} {chunk.title} {chunk.section} {chunk.text} {' '.join(chunk.tags)}")
            for chunk in self.chunks
        ]
        self._index = BM25Index(documents)
        if self.embedder is not None:
            self.vectors = self.store.load_vectors(getattr(self.embedder, "model", "default"))
            if not self.vectors:
                self.vectors = {}
        return self

    def build_embeddings(self, batch_size: int = 32) -> int:
        """Embed every chunk with the configured backend. Returns vectors written."""

        if self.embedder is None:
            raise RuntimeError("no embedding backend configured")
        if not self.chunks:
            self.refresh()
        model = getattr(self.embedder, "model", "default")
        stored: dict[str, list[float]] = {}
        for start in range(0, len(self.chunks), batch_size):
            batch = self.chunks[start : start + batch_size]
            vectors = self.embedder.embed([c.text for c in batch])
            stored.update({chunk.id: vector for chunk, vector in zip(batch, vectors, strict=True)})
        self.store.save_vectors(model, stored)
        self.vectors = stored
        return len(stored)

    # ----------------------------------------------------------------- search
    def search(self, query: str, top_k: int = 5) -> list[Passage]:
        if self._index is None or not self.chunks:
            self.refresh()
        assert self._index is not None  # narrowed by refresh()
        tokens = tokenize(query)
        groups = concept_groups(query)
        lexical = dict(self._index.search(flatten(groups) or tokens, limit=max(top_k * 4, 20)))
        dense: dict[str, float] = {}
        if self.dense_enabled and self.embedder is not None:
            try:
                query_vector = self.embedder.embed([query])[0]
            except Exception:  # pragma: no cover - network dependent
                query_vector = None
            if query_vector:
                for chunk in self.chunks:
                    vector = self.vectors.get(chunk.id)
                    if vector:
                        dense[chunk.id] = max(0.0, cosine(query_vector, vector))

        candidates = set(lexical) | set(sorted(dense, key=dense.get, reverse=True)[: max(top_k * 4, 20)])
        if not candidates:
            return []

        use_dense = bool(dense)
        weight = self.bm25_weight if use_dense else 1.0
        scored: list[tuple[int, float, float, float]] = []
        for index in candidates:
            raw = lexical.get(index, 0.0)
            # Saturating BM25 keeps absolute evidence comparable across queries; the
            # IDF coverage factor keeps partially-matching documents from scoring high.
            saturation = raw / (raw + 3.0) if raw else 0.0
            normalised = self._index.concept_coverage(groups, index) * saturation
            dense_score = dense.get(self.chunks[index].id, 0.0)
            fused = weight * normalised + (1 - weight) * dense_score
            scored.append((index, fused, raw, dense_score))

        scored.sort(key=lambda item: item[1], reverse=True)
        results: list[Passage] = []
        for index, fused, raw, dense_score in scored:
            if fused < self.min_score:
                continue
            chunk = self.chunks[index]
            results.append(
                Passage(
                    chunk_id=chunk.id,
                    doc_id=chunk.doc_id,
                    title=chunk.title,
                    section=chunk.section,
                    text=chunk.text,
                    score=round(fused, 4),
                    bm25=round(raw, 4),
                    dense=round(dense_score, 4),
                    tags=list(chunk.tags),
                    sources=[SourceRef(**source) for source in chunk.sources],
                )
            )
            if len(results) >= top_k:
                break
        return results
