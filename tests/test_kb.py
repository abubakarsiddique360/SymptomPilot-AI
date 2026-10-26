from __future__ import annotations

from pathlib import Path

import pytest

from symptompilot.retrieval.kb import KnowledgeError, load_documents, parse_document

EXPECTED_TOPICS = {
    "triage-basics",
    "chest-pain",
    "breathing-difficulty",
    "fever",
    "headache",
    "stroke-recognition",
    "abdominal-pain",
    "vomiting-diarrhoea",
    "severe-allergic-reaction",
    "mental-health-crisis",
    "back-pain",
    "urinary-symptoms",
    "common-cold-flu",
    "anxiety-panic",
}


def test_bundled_knowledge_base_is_valid(knowledge_dir: Path) -> None:
    kb = load_documents(knowledge_dir)
    assert {document.doc_id for document in kb.documents} == EXPECTED_TOPICS
    for document in kb.documents:
        assert document.title
        assert document.summary
        assert document.sources, f"{document.doc_id} needs at least one source"
        assert document.body.strip()
        assert document.checksum


def test_missing_frontmatter_raises(knowledge_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "broken.md"
    broken.write_text("# No frontmatter here", encoding="utf-8")
    with pytest.raises(KnowledgeError):
        parse_document(broken)


def test_duplicate_ids_raise(tmp_path: Path) -> None:
    page = "---\nid: dup\ntitle: Duplicate\n---\n\nBody text."
    (tmp_path / "a.md").write_text(page, encoding="utf-8")
    (tmp_path / "b.md").write_text(page, encoding="utf-8")
    with pytest.raises(KnowledgeError):
        load_documents(tmp_path)


def test_missing_directory_returns_empty_base(tmp_path: Path) -> None:
    assert len(load_documents(tmp_path / "does-not-exist")) == 0
