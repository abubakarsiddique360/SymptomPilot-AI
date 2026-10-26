from __future__ import annotations

from pathlib import Path

import pytest

from symptompilot.retrieval.embedder import OllamaEmbedder, cosine
from symptompilot.retrieval.expansion import concept_groups, flatten


def test_concept_groups_expand_lay_terms() -> None:
    groups = concept_groups("it burns when I pee")
    flat = flatten(groups)
    assert "pee" in flat
    assert "urine" in flat
    assert "burn" in flat


def test_concept_groups_are_unique() -> None:
    groups = concept_groups("pain pain pain")
    assert len(groups) == 1


def test_cosine_bounds() -> None:
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([], [1.0]) == 0.0
    assert cosine([1.0, 2.0], [1.0]) == 0.0


def test_embedder_raises_when_unreachable(monkeypatch) -> None:
    import httpx

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("symptompilot.retrieval.embedder.httpx.post", boom)
    from symptompilot.retrieval.embedder import EmbeddingUnavailable

    with pytest.raises(EmbeddingUnavailable):
        OllamaEmbedder("http://localhost:11434", "model").embed(["text"])


def test_retriever_falls_back_when_embeddings_missing(settings, monkeypatch) -> None:
    from symptompilot.retrieval.hybrid import HybridRetriever
    from symptompilot.retrieval.kb import load_documents
    from symptompilot.retrieval.store import KnowledgeStore

    class BrokenEmbedder:
        model = "broken"

        def embed(self, texts):
            raise RuntimeError("unavailable")

    store = KnowledgeStore(settings.db_path)
    store.ingest(load_documents(settings.kb_dir))
    retriever = HybridRetriever(store, embedder=BrokenEmbedder()).refresh()  # type: ignore[arg-type]
    retriever.vectors = {"anything": [1.0]}
    passages = retriever.search("sore throat", top_k=2)
    assert passages
    assert passages[0].doc_id == "common-cold-flu"


def test_knowledge_dir_fixture_points_at_repo(knowledge_dir: Path) -> None:
    assert (knowledge_dir / "triage-basics.md").exists()
