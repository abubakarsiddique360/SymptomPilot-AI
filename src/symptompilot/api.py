"""FastAPI application."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from symptompilot import __version__
from symptompilot.config import Settings
from symptompilot.models import (
    HealthReport,
    SearchHit,
    TriageRequest,
    TriageResponse,
)
from symptompilot.retrieval.kb import load_documents
from symptompilot.runtime import Runtime, build_runtime

WEB_DIR = Path(__file__).parent / "web"


def _clean_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in history[-12:]:
        role = item.get("role", "")
        content = item.get("content", "")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            cleaned.append({"role": role, "content": content[:2000]})
    return cleaned


def create_app(settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime = runtime or build_runtime(settings)
        yield

    app = FastAPI(
        title="SymptomPilot API",
        version=__version__,
        description=(
            "Local-first symptom triage with hybrid retrieval, deterministic red-flag "
            "screening and citation-bound answers. Educational use only."
        ),
        lifespan=lifespan,
    )
    resolved = settings or (runtime.settings if runtime else Settings.from_env())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    def get_runtime() -> Runtime:
        instance = getattr(app.state, "runtime", None)
        if instance is None:  # pragma: no cover - lifespan always sets it
            raise HTTPException(status_code=503, detail="runtime not initialised")
        return instance

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def index() -> HTMLResponse:
        return HTMLResponse((WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8"))

    @app.get("/api/health", response_model=HealthReport, tags=["system"])
    def health() -> HealthReport:
        current = get_runtime()
        stats = current.store.stats()
        return HealthReport(
            status="ok",
            version=__version__,
            llm_mode="llm" if current.llm else "extractive",
            llm_provider=current.llm.name if current.llm else None,
            dense_retrieval=current.retriever.dense_enabled,
            documents=stats["documents"],
            chunks=stats["chunks"],
            knowledge_dir=str(current.settings.kb_dir),
        )

    @app.post("/api/triage", response_model=TriageResponse, tags=["triage"])
    def triage(payload: TriageRequest) -> TriageResponse:
        current = get_runtime()
        return current.agent.triage(
            message=payload.message,
            history=_clean_history(payload.history),
            top_k=payload.top_k,
        )

    @app.post("/api/triage/stream", tags=["triage"])
    async def triage_stream(payload: TriageRequest) -> StreamingResponse:
        current = get_runtime()
        result = await run_in_threadpool(
            current.agent.triage,
            payload.message,
            _clean_history(payload.history),
            payload.top_k,
        )

        async def events() -> AsyncIterator[bytes]:
            meta = result.model_dump(exclude={"answer"})
            yield _sse("meta", meta)
            for chunk in _text_chunks(result.answer):
                yield _sse("token", {"text": chunk})
                await asyncio.sleep(0)
            yield _sse("done", {"latency_ms": result.latency_ms})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/search", response_model=list[SearchHit], tags=["retrieval"])
    def search(payload: TriageRequest) -> list[SearchHit]:
        current = get_runtime()
        passages = current.retriever.search(payload.message, top_k=payload.top_k or 5)
        return [
            SearchHit(
                chunk_id=passage.chunk_id,
                doc_id=passage.doc_id,
                title=passage.title,
                section=passage.section,
                score=passage.score,
                snippet=passage.text[:280],
            )
            for passage in passages
        ]

    @app.get("/api/topics", tags=["knowledge"])
    def topics() -> list[dict]:
        current = get_runtime()
        return [
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "topic": document.topic,
                "summary": document.summary,
                "tags": list(document.tags),
                "sources": [source.model_dump() for source in document.sources],
            }
            for document in current.store.load_documents()
        ]

    @app.get("/api/topics/{doc_id}", tags=["knowledge"])
    def topic(doc_id: str) -> dict:
        current = get_runtime()
        stored = next(
            (d for d in current.store.load_documents() if d.doc_id == doc_id),
            None,
        )
        if stored is None:
            raise HTTPException(status_code=404, detail="unknown topic")
        body = ""
        for document in load_documents(current.settings.kb_dir).documents:
            if document.doc_id == doc_id:
                body = document.body
                break
        return {
            "doc_id": stored.doc_id,
            "title": stored.title,
            "topic": stored.topic,
            "summary": stored.summary,
            "tags": list(stored.tags),
            "sources": [source.model_dump() for source in stored.sources],
            "body": body,
        }

    return app


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


def _text_chunks(text: str, size: int = 24) -> list[str]:
    words = text.split(" ")
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) >= size:
            chunks.append(candidate)
            current = ""
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


app = create_app()
