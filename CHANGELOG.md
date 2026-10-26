# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-26

### Added

- Deterministic red-flag screener with 27 rules, four urgency levels, negation
  handling and compound-sign matching. Runs before any model call.
- Hybrid retrieval over SQLite: dependency-free Okapi BM25 with IDF-weighted
  concept coverage, lay-vocabulary expansion, and optional Ollama embeddings
  blended by cosine similarity.
- Agent pipeline: screen â†’ retrieve â†’ compose â†’ verify, with citation
  enforcement, marker stripping for unsupported claims and an abstain path for
  out-of-scope questions.
- Three answering modes: local Ollama model, any OpenAI-compatible endpoint, or a
  fully offline extractive composer that copies sentences straight from evidence.
- FastAPI service with `/api/health`, `/api/triage`, `/api/triage/stream` (SSE),
  `/api/search` and knowledge-base endpoints.
- Single-page web UI: urgency banner, cited evidence cards, follow-up question
  chips, dark/light theme, keyboard-friendly composer.
- CLI (`symptompilot serve | ingest | ask | topics | eval`) and `python -m symptompilot`.
- Offline evaluation harness with 18 golden cases measuring level accuracy,
  retrieval hit rate, emergency recall and abstention accuracy.
- 14 original knowledge-base pages with cited public-health references.
- Packaging, Dockerfile, Compose file, GitHub Actions CI (3.10â€“3.12), issue and
  PR templates, contributing guide, code of conduct and security policy.

[Unreleased]: https://github.com/abubakarsiddique360/SymptomPilot-AI/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/abubakarsiddique360/SymptomPilot-AI/releases/tag/v0.1.0
