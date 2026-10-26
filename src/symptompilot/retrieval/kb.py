"""Knowledge-base loading.

Pages are plain markdown files with a YAML frontmatter block::

    ---
    id: chest-pain
    title: Chest pain and pressure
    topic: Cardiovascular
    tags: [chest, pain]
    sources:
      - title: Chest pain
        url: https://example.org
        publisher: Example
    ---

Only the frontmatter is parsed as YAML; the body stays markdown so the same
files read well on GitHub and are easy to contribute to.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from symptompilot.models import SourceRef


class KnowledgeError(RuntimeError):
    """Raised when a knowledge-base page is malformed."""


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    topic: str
    summary: str
    tags: tuple[str, ...]
    sources: tuple[SourceRef, ...]
    body: str
    path: str
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            digest = hashlib.sha256(f"{self.doc_id}:{self.body}".encode()).hexdigest()
            object.__setattr__(self, "checksum", digest[:16])


@dataclass
class KnowledgeBase:
    documents: list[Document] = field(default_factory=list)

    def by_id(self, doc_id: str) -> Document | None:
        return next((d for d in self.documents if d.doc_id == doc_id), None)

    def __len__(self) -> int:
        return len(self.documents)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        raise KnowledgeError("missing YAML frontmatter")
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        raise KnowledgeError("unterminated YAML frontmatter")
    return yaml.safe_load(parts[1]) or {}, parts[2].strip()


def parse_document(path: Path) -> Document:
    meta, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    doc_id = str(meta.get("id") or path.stem).strip()
    if not doc_id:
        raise KnowledgeError(f"{path.name}: empty id")
    sources_raw = meta.get("sources") or []
    if not isinstance(sources_raw, list):
        raise KnowledgeError(f"{path.name}: sources must be a list")
    sources = tuple(
        SourceRef(
            title=str(item.get("title", "")).strip(),
            url=str(item.get("url", "")).strip(),
            publisher=str(item.get("publisher", "")).strip(),
        )
        for item in sources_raw
        if isinstance(item, dict)
    )
    return Document(
        doc_id=doc_id,
        title=str(meta.get("title") or doc_id).strip(),
        topic=str(meta.get("topic") or "General").strip(),
        summary=str(meta.get("summary") or "").strip(),
        tags=tuple(str(t).strip() for t in meta.get("tags") or () if str(t).strip()),
        sources=sources,
        body=body,
        path=str(path),
    )


def load_documents(kb_dir: Path | str) -> KnowledgeBase:
    directory = Path(kb_dir)
    if not directory.exists():
        return KnowledgeBase()
    documents: list[Document] = []
    seen: set[str] = set()
    for path in sorted(directory.rglob("*.md")):
        document = parse_document(path)
        if document.doc_id in seen:
            raise KnowledgeError(f"duplicate knowledge-base id: {document.doc_id}")
        seen.add(document.doc_id)
        documents.append(document)
    return KnowledgeBase(documents=documents)
