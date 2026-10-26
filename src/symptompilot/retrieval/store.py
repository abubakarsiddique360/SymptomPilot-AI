"""SQLite persistence for documents, chunks and optional dense vectors."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from symptompilot.retrieval.chunker import Chunk, chunk_document
from symptompilot.retrieval.kb import Document, KnowledgeBase

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    topic       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    sources     TEXT NOT NULL DEFAULT '[]',
    path        TEXT NOT NULL DEFAULT '',
    checksum    TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    section     TEXT NOT NULL,
    text        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    position    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE TABLE IF NOT EXISTS vectors (
    chunk_id    TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    dim         INTEGER NOT NULL,
    vector      TEXT NOT NULL,
    PRIMARY KEY (chunk_id, model)
);
CREATE TABLE IF NOT EXISTS meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    doc_id: str
    title: str
    section: str
    text: str
    tags: tuple[str, ...]
    sources: tuple[dict, ...]


@dataclass(frozen=True)
class IngestReport:
    documents: int
    chunks: int
    added: int
    updated: int
    removed: int

    def as_dict(self) -> dict[str, int]:
        return {
            "documents": self.documents,
            "chunks": self.chunks,
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed,
        }


class KnowledgeStore:
    """Thin, explicit SQLite wrapper — no ORM, no hidden state."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def is_empty(self) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
        return not row or row["n"] == 0

    def ingest(self, kb: KnowledgeBase) -> IngestReport:
        """Synchronise the database with a knowledge base (idempotent)."""

        self.initialize()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        added = updated = removed = chunk_total = 0
        incoming = {document.doc_id: document for document in kb.documents}
        with self.connect() as connection:
            existing = {
                row["id"]: row["checksum"] for row in connection.execute("SELECT id, checksum FROM documents")
            }
            for document in kb.documents:
                if existing.get(document.doc_id) == document.checksum:
                    continue
                chunks = self._chunks_for(document)
                connection.execute(
                    """
                    INSERT INTO documents (id, title, topic, summary, tags, sources, path, checksum, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title,
                        topic=excluded.topic,
                        summary=excluded.summary,
                        tags=excluded.tags,
                        sources=excluded.sources,
                        path=excluded.path,
                        checksum=excluded.checksum,
                        updated_at=excluded.updated_at
                    """,
                    (
                        document.doc_id,
                        document.title,
                        document.topic,
                        document.summary,
                        json.dumps(list(document.tags)),
                        json.dumps([s.model_dump() for s in document.sources]),
                        document.path,
                        document.checksum,
                        now,
                    ),
                )
                connection.execute("DELETE FROM chunks WHERE doc_id = ?", (document.doc_id,))
                connection.executemany(
                    "INSERT INTO chunks (id, doc_id, title, section, text, tags, position) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            chunk.id,
                            chunk.doc_id,
                            chunk.title,
                            chunk.section,
                            chunk.text,
                            json.dumps(list(chunk.tags)),
                            position,
                        )
                        for position, chunk in enumerate(chunks)
                    ],
                )
                chunk_total += len(chunks)
                if document.doc_id in existing:
                    updated += 1
                else:
                    added += 1

            for doc_id in set(existing) - set(incoming):
                connection.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                removed += 1

            connection.execute("DELETE FROM vectors WHERE chunk_id NOT IN (SELECT id FROM chunks)")
            connection.execute(
                "INSERT INTO meta (key, value) VALUES ('last_ingest', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (now,),
            )
            documents = connection.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
            chunks = connection.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]

        return IngestReport(
            documents=documents,
            chunks=chunks,
            added=added,
            updated=updated,
            removed=removed,
        )

    @staticmethod
    def _chunks_for(document: Document) -> list[Chunk]:
        return chunk_document(
            doc_id=document.doc_id,
            title=document.title,
            markdown=document.body,
            tags=document.tags,
        )

    def load_chunks(self) -> list[ChunkRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.doc_id, c.title, c.section, c.text, c.tags, d.sources
                FROM chunks c JOIN documents d ON d.id = c.doc_id
                ORDER BY c.doc_id, c.position
                """
            ).fetchall()
        return [
            ChunkRecord(
                id=row["id"],
                doc_id=row["doc_id"],
                title=row["title"],
                section=row["section"],
                text=row["text"],
                tags=tuple(json.loads(row["tags"] or "[]")),
                sources=tuple(json.loads(row["sources"] or "[]")),
            )
            for row in rows
        ]

    def load_documents(self) -> list[Document]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM documents ORDER BY id").fetchall()
        from symptompilot.models import SourceRef

        return [
            Document(
                doc_id=row["id"],
                title=row["title"],
                topic=row["topic"],
                summary=row["summary"],
                tags=tuple(json.loads(row["tags"] or "[]")),
                sources=tuple(SourceRef(**s) for s in json.loads(row["sources"] or "[]")),
                body="",
                path=row["path"],
                checksum=row["checksum"],
            )
            for row in rows
        ]

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            documents = connection.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"]
            chunks = connection.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"]
            vectors = connection.execute("SELECT COUNT(*) AS n FROM vectors").fetchone()["n"]
        return {"documents": documents, "chunks": chunks, "vectors": vectors}

    def save_vectors(self, model: str, vectors: dict[str, list[float]]) -> int:
        with self.connect() as connection:
            connection.executemany(
                "INSERT INTO vectors (chunk_id, model, dim, vector) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(chunk_id, model) DO UPDATE SET dim=excluded.dim, vector=excluded.vector",
                [(chunk_id, model, len(vec), json.dumps(vec)) for chunk_id, vec in vectors.items()],
            )
        return len(vectors)

    def load_vectors(self, model: str) -> dict[str, list[float]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT chunk_id, vector FROM vectors WHERE model = ?", (model,)
            ).fetchall()
        return {row["chunk_id"]: json.loads(row["vector"]) for row in rows}
