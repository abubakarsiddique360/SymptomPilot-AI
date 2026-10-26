"""Command-line interface."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from symptompilot import __version__
from symptompilot.config import Settings
from symptompilot.evaluation.runner import DEFAULT_CASES, run_evaluation
from symptompilot.retrieval.embedder import OllamaEmbedder
from symptompilot.runtime import build_runtime, sync_knowledge


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    overrides = {}
    if getattr(args, "kb", None):
        overrides["kb_dir"] = Path(args.kb)
    if getattr(args, "db", None):
        overrides["db_path"] = Path(args.db)
    return dataclasses.replace(settings, **overrides) if overrides else settings


def cmd_ingest(args: argparse.Namespace) -> int:
    settings = _settings(args)
    report = sync_knowledge(settings)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(
            f"Indexed {report.documents} documents into {report.chunks} chunks "
            f"(added {report.added}, updated {report.updated}, removed {report.removed})."
        )
    if args.embed:
        from symptompilot.retrieval.hybrid import HybridRetriever
        from symptompilot.retrieval.store import KnowledgeStore

        embedder = OllamaEmbedder(settings.ollama_url, settings.embed_model)
        if not embedder.available():
            print("Ollama is not reachable; skipping dense embeddings.", file=sys.stderr)
            return 0
        retriever = HybridRetriever(KnowledgeStore(settings.db_path), embedder=embedder).refresh()
        written = retriever.build_embeddings()
        print(f"Stored {written} dense vectors using {settings.embed_model}.")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    settings = _settings(args)
    runtime = build_runtime(settings)
    response = runtime.agent.triage(" ".join(args.message), top_k=args.top_k)
    if args.json:
        print(response.model_dump_json(indent=2))
        return 0
    print(response.answer)
    print()
    print(f"Urgency : {response.urgency.level} ({response.urgency.score})")
    print(f"Mode    : {response.mode}")
    if response.citations:
        print("Evidence:")
        for citation in response.citations:
            print(f"  [{citation.marker}] {citation.title} > {citation.section} ({citation.score:.3f})")
    if response.follow_up_questions:
        print("Follow-ups:")
        for question in response.follow_up_questions:
            print(f"  - {question}")
    print()
    print(response.disclaimer)
    return 0


def cmd_topics(args: argparse.Namespace) -> int:
    runtime = build_runtime(_settings(args))
    documents = runtime.store.load_documents()
    if args.json:
        payload = [
            {
                "doc_id": document.doc_id,
                "title": document.title,
                "topic": document.topic,
                "summary": document.summary,
                "tags": list(document.tags),
            }
            for document in documents
        ]
        print(json.dumps(payload, indent=2))
        return 0
    for document in documents:
        print(f"{document.doc_id:<24} {document.topic:<18} {document.title}")
    print(f"\n{len(documents)} topics")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    runtime = build_runtime(_settings(args))
    report = run_evaluation(runtime.agent, cases_path=args.cases)
    print(report.to_json() if args.json else report.summary())
    return 0 if report.passed else 1


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(
        "symptompilot.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="symptompilot",
        description="Local-first symptom triage assistant (educational use only).",
    )
    parser.add_argument("--version", action="version", version=f"symptompilot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--kb", help="knowledge-base directory (default: ./knowledge)")
        target.add_argument("--db", help="SQLite database path (default: ./var/symptompilot.db)")

    serve = sub.add_parser("serve", help="run the web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    serve.add_argument("--log-level", default="info")
    add_common(serve)
    serve.set_defaults(func=cmd_serve)

    ingest = sub.add_parser("ingest", help="build or refresh the SQLite index")
    ingest.add_argument("--embed", action="store_true", help="also build dense vectors with Ollama")
    ingest.add_argument("--json", action="store_true")
    add_common(ingest)
    ingest.set_defaults(func=cmd_ingest)

    ask = sub.add_parser("ask", help="ask a single question from the terminal")
    ask.add_argument("message", nargs="+")
    ask.add_argument("--top-k", type=int, default=None)
    ask.add_argument("--json", action="store_true")
    add_common(ask)
    ask.set_defaults(func=cmd_ask)

    topics = sub.add_parser("topics", help="list knowledge-base topics")
    topics.add_argument("--json", action="store_true")
    add_common(topics)
    topics.set_defaults(func=cmd_topics)

    evaluate = sub.add_parser("eval", help="run the offline evaluation suite")
    evaluate.add_argument("--cases", default=str(DEFAULT_CASES))
    evaluate.add_argument("--json", action="store_true")
    add_common(evaluate)
    evaluate.set_defaults(func=cmd_eval)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows consoles often default to a legacy code page; transcripts contain
    # typographic characters that would otherwise raise UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
