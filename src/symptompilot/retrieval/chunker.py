"""Markdown-aware chunking.

Headings become section labels so every retrieved passage can be cited as
``Document › Section`` instead of an opaque chunk id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)$")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    title: str
    section: str
    text: str
    tags: tuple[str, ...] = ()


def split_sections(markdown: str) -> list[tuple[str, str]]:
    """Split a markdown body into ``(heading, text)`` pairs."""

    sections: list[tuple[str, str]] = []
    heading = "Overview"
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((heading, body))

    for line in markdown.splitlines():
        match = _HEADING_RE.match(line.strip())
        if match:
            flush()
            heading = match.group(2).strip().rstrip("#").strip() or "Overview"
            buffer = []
        else:
            buffer.append(line)
    flush()
    return sections


def _pack(paragraphs: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not paragraph:
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
        else:  # a single oversized paragraph: fall back to sentence windows
            sentences = _SENTENCE_RE.split(paragraph)
            window = ""
            for sentence in sentences:
                if len(window) + len(sentence) + 1 <= max_chars:
                    window = f"{window} {sentence}".strip()
                else:
                    if window:
                        pieces.append(window)
                    window = sentence[-max_chars:]
            current = window
        if overlap_chars and pieces:
            tail = pieces[-1][-overlap_chars:]
            current = f"{tail} {current}".strip()
    if current:
        pieces.append(current)
    return [p.strip() for p in pieces if p.strip()]


def chunk_document(
    doc_id: str,
    title: str,
    markdown: str,
    tags: tuple[str, ...] | list[str] = (),
    max_chars: int = 900,
    overlap_chars: int = 140,
) -> list[Chunk]:
    """Turn one knowledge-base page into citable chunks."""

    tag_tuple = tuple(tags)
    chunks: list[Chunk] = []
    for section, text in split_sections(markdown):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for piece in _pack(paragraphs, max_chars, overlap_chars):
            chunks.append(
                Chunk(
                    id=f"{doc_id}#{len(chunks)}",
                    doc_id=doc_id,
                    title=title,
                    section=section,
                    text=piece,
                    tags=tag_tuple,
                )
            )
    return chunks
