from __future__ import annotations

from symptompilot.retrieval.hybrid import HybridRetriever
from symptompilot.retrieval.store import KnowledgeStore


def test_search_returns_relevant_document(runtime) -> None:
    passages = runtime.retriever.search("crushing chest pain and sweating", top_k=3)
    assert passages
    assert passages[0].doc_id == "chest-pain"
    assert passages[0].score >= passages[-1].score


def test_search_respects_top_k(runtime) -> None:
    passages = runtime.retriever.search("fever and chills", top_k=2)
    assert 0 < len(passages) <= 2


def test_search_filters_unrelated_queries(runtime) -> None:
    assert runtime.retriever.search("quantum chromodynamics lattice", top_k=3) == []


def test_dense_disabled_without_vectors(runtime) -> None:
    assert runtime.retriever.dense_enabled is False


def test_store_ingest_is_idempotent(settings) -> None:
    from symptompilot.retrieval.kb import load_documents

    store = KnowledgeStore(settings.db_path)
    kb = load_documents(settings.kb_dir)
    first = store.ingest(kb)
    second = store.ingest(kb)
    assert first.documents == second.documents
    assert second.added == 0
    assert second.updated == 0
    assert store.stats()["chunks"] == first.chunks


def test_retriever_reports_sources(runtime) -> None:
    passages = runtime.retriever.search("stroke face drooping", top_k=2)
    assert passages
    assert all(isinstance(p.sources, list) for p in passages)
    assert any(passage.sources for passage in passages)


def test_refresh_rebuilds_index(runtime) -> None:
    retriever: HybridRetriever = runtime.retriever
    assert retriever.chunks
    retriever.refresh()
    assert retriever.search("sore throat", top_k=1)
