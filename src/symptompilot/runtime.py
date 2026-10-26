"""Wiring: build a ready-to-use runtime from settings.

The runtime object is deliberately small and injected everywhere, so tests can
swap the store, retriever or LLM without patching globals.
"""

from __future__ import annotations

from dataclasses import dataclass

from symptompilot.agent.orchestrator import TriageAgent
from symptompilot.config import Settings
from symptompilot.llm import resolve_client
from symptompilot.llm.base import LLMClient
from symptompilot.retrieval.embedder import OllamaEmbedder
from symptompilot.retrieval.hybrid import HybridRetriever
from symptompilot.retrieval.kb import KnowledgeBase, load_documents
from symptompilot.retrieval.store import IngestReport, KnowledgeStore
from symptompilot.safety.redflags import RedFlagEngine


@dataclass
class Runtime:
    settings: Settings
    store: KnowledgeStore
    retriever: HybridRetriever
    engine: RedFlagEngine
    agent: TriageAgent
    llm: LLMClient | None


def build_runtime(
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    embedder: object | None = None,
) -> Runtime:
    settings = settings or Settings.from_env()
    store = KnowledgeStore(settings.db_path)
    store.initialize()

    knowledge: KnowledgeBase = load_documents(settings.kb_dir)
    if knowledge.documents:
        store.ingest(knowledge)

    if embedder is None and settings.embed_backend != "none":
        embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model)

    retriever = HybridRetriever(
        store=store,
        embedder=embedder,  # type: ignore[arg-type]
        bm25_weight=settings.bm25_weight,
        min_score=settings.min_chunk_score,
    ).refresh()

    engine = RedFlagEngine.from_yaml()
    client = llm if llm is not None else resolve_client(settings)
    agent = TriageAgent(retriever=retriever, engine=engine, settings=settings, llm=client)
    return Runtime(
        settings=settings,
        store=store,
        retriever=retriever,
        engine=engine,
        agent=agent,
        llm=client,
    )


def sync_knowledge(settings: Settings | None = None) -> IngestReport:
    settings = settings or Settings.from_env()
    store = KnowledgeStore(settings.db_path)
    return store.ingest(load_documents(settings.kb_dir))
