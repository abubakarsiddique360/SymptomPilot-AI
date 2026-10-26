"""Shared data models (Pydantic v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UrgencyLevel = Literal["emergency", "urgent", "routine", "unknown"]

Level_score = {"emergency": 100, "urgent": 60, "routine": 25, "unknown": 10}


class SourceRef(BaseModel):
    """A pointer to the public guidance a knowledge-base page was derived from."""

    title: str
    url: str
    publisher: str = ""


class RedFlag(BaseModel):
    id: str
    label: str
    level: Literal["emergency", "urgent", "routine"]
    advice: str
    matched_text: str


class Urgency(BaseModel):
    level: UrgencyLevel
    score: int = 0
    headline: str = ""
    actions: list[str] = Field(default_factory=list)


class ScreenResult(BaseModel):
    urgency: Urgency
    flags: list[RedFlag] = Field(default_factory=list)

    @property
    def is_emergency(self) -> bool:
        return self.urgency.level == "emergency"


class Passage(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    score: float
    bm25: float = 0.0
    dense: float = 0.0
    tags: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


class Citation(BaseModel):
    marker: str
    doc_id: str
    title: str
    section: str
    snippet: str
    score: float
    sources: list[SourceRef] = Field(default_factory=list)


class Verification(BaseModel):
    cited_markers: list[str] = Field(default_factory=list)
    invalid_markers: list[str] = Field(default_factory=list)
    evidence_supplied: int = 0
    notes: list[str] = Field(default_factory=list)


class TriageRequest(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    top_k: int | None = Field(default=None, ge=1, le=10)


class TriageResponse(BaseModel):
    answer: str
    mode: str
    abstained: bool = False
    urgency: Urgency
    red_flags: list[RedFlag] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    verification: Verification = Field(default_factory=Verification)
    latency_ms: int = 0
    disclaimer: str = ""


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    score: float
    snippet: str


class TopicSummary(BaseModel):
    doc_id: str
    title: str
    topic: str
    summary: str
    tags: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)


class HealthReport(BaseModel):
    status: str = "ok"
    version: str
    llm_mode: str
    llm_provider: str | None = None
    dense_retrieval: bool
    documents: int
    chunks: int
    knowledge_dir: str
