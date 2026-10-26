from __future__ import annotations

from symptompilot.retrieval.chunker import chunk_document, split_sections

SAMPLE = """
Intro paragraph before any heading.

## First section

Short paragraph.

## Second section

Another paragraph that is also short.
"""


def test_split_sections_uses_headings() -> None:
    sections = split_sections(SAMPLE)
    names = [name for name, _ in sections]
    assert names == ["Overview", "First section", "Second section"]


def test_chunks_are_citable_and_unique() -> None:
    chunks = chunk_document("demo", "Demo page", SAMPLE, tags=["demo"])
    assert chunks
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    assert all(chunk.doc_id == "demo" for chunk in chunks)
    assert all(chunk.title == "Demo page" for chunk in chunks)
    assert chunks[0].id.startswith("demo#")


def test_chunks_respect_size_limit() -> None:
    body = "\n\n".join(f"Sentence number {i} about chest pain." for i in range(60))
    chunks = chunk_document("big", "Big page", f"## Section\n\n{body}", max_chars=300, overlap_chars=40)
    assert chunks
    assert max(len(chunk.text) for chunk in chunks) < 700


def test_long_paragraph_is_split_on_sentences() -> None:
    long_paragraph = " ".join(f"This is sentence {i} describing a symptom." for i in range(40))
    chunks = chunk_document("long", "Long page", long_paragraph, max_chars=200, overlap_chars=0)
    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)


def test_empty_body_produces_no_chunks() -> None:
    assert chunk_document("empty", "Empty", "\n\n") == []
