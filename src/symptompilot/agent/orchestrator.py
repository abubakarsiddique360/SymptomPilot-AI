"""The triage orchestrator.

Pipeline: screen → retrieve → compose → verify. The screen step is deterministic
and runs first so urgency can never be produced by generated text.
"""

from __future__ import annotations

import time

from symptompilot.agent.composer import compose
from symptompilot.agent.prompts import SYSTEM_PROMPT, build_user_prompt
from symptompilot.agent.verifier import verify
from symptompilot.config import Settings
from symptompilot.llm.base import LLMClient, LLMError
from symptompilot.models import (
    Citation,
    Passage,
    RedFlag,
    ScreenResult,
    TriageResponse,
)
from symptompilot.retrieval.hybrid import HybridRetriever
from symptompilot.safety.redflags import RedFlagEngine

DURATION_HINTS = (
    "since",
    "yesterday",
    "today",
    "day",
    "days",
    "week",
    "weeks",
    "hour",
    "hours",
    "month",
    "started",
    "sudden",
    "constant",
)
SEVERITY_HINTS = ("severe", "mild", "moderate", "worst", "sharp", "dull", "/10", "unbearable", "slight")
ASSOCIATED_HINTS = ("fever", "vomit", "dizz", "breath", "nausea", "sweat", "rash", "chill", "cough")
CONTEXT_HINTS = (
    "year old",
    "years old",
    "pregnant",
    "diabet",
    "asthma",
    "condition",
    "medication",
    "medicine",
    "tablet",
    "pill",
    "allerg",
)


class TriageAgent:
    def __init__(
        self,
        retriever: HybridRetriever,
        engine: RedFlagEngine | None = None,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.retriever = retriever
        self.engine = engine or RedFlagEngine.from_yaml()
        self.settings = settings or Settings()
        self.llm = llm

    # ------------------------------------------------------------------ public
    def triage(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        top_k: int | None = None,
    ) -> TriageResponse:
        started = time.perf_counter()
        history = history or []
        screen = self.engine.screen(message)
        query = self._search_query(message, history)
        passages = self._prioritise(self.retriever.search(query, top_k=top_k or self.settings.top_k), screen)
        abstained = self._should_abstain(passages)
        citations = [] if abstained else self._citations(passages)

        answer, mode = self._compose(message, passages, screen, abstained, history)
        answer, verification = verify(answer, citations, screen.urgency.level)

        return TriageResponse(
            answer=answer,
            mode=mode,
            abstained=abstained,
            urgency=screen.urgency,
            red_flags=screen.flags,
            citations=citations,
            follow_up_questions=self.follow_up_questions(message, screen.flags),
            verification=verification,
            latency_ms=int((time.perf_counter() - started) * 1000),
            disclaimer=self.settings.disclaimer,
        )

    def follow_up_questions(
        self,
        message: str,
        flags: list[RedFlag],
        limit: int = 3,
    ) -> list[str]:
        questions: list[str] = list(self.engine.questions_for(flags))
        lowered = message.lower()
        if not any(hint in lowered for hint in DURATION_HINTS):
            questions.append("When did this start, and is it constant or coming and going?")
        if not any(hint in lowered for hint in SEVERITY_HINTS):
            questions.append("How severe is it right now — mild, moderate, or severe?")
        if not any(hint in lowered for hint in ASSOCIATED_HINTS):
            questions.append("Any fever, vomiting, dizziness, sweating, or trouble breathing with it?")
        if not any(hint in lowered for hint in CONTEXT_HINTS):
            questions.append(
                "What is the person's age, and are they pregnant or living with a long-term condition?"
            )
        deduped: list[str] = []
        for question in questions:
            if question not in deduped:
                deduped.append(question)
        return deduped[:limit]

    # ----------------------------------------------------------------- helpers
    def _search_query(self, message: str, history: list[dict[str, str]]) -> str:
        if len(message.split()) >= 5:
            return message
        previous = [item for item in history if item.get("role") == "user"]
        if previous:
            return f"{previous[-1].get('content', '')} {message}".strip()
        return message

    def _should_abstain(self, passages: list[Passage]) -> bool:
        if not passages:
            return True
        return passages[0].score < self.settings.abstain_threshold

    def _prioritise(self, passages: list[Passage], screen: ScreenResult) -> list[Passage]:
        """Lift pages tied to a matched red flag without reordering the rest."""

        preferred = self.engine.preferred_docs(screen.flags)
        if not preferred:
            return passages
        return sorted(passages, key=lambda passage: 0 if passage.doc_id in preferred else 1)

    @staticmethod
    def _citations(passages: list[Passage]) -> list[Citation]:
        return [
            Citation(
                marker=f"S{index}",
                doc_id=passage.doc_id,
                title=passage.title,
                section=passage.section,
                snippet=passage.text[:400],
                score=passage.score,
                sources=passage.sources,
            )
            for index, passage in enumerate(passages, start=1)
        ]

    def _compose(
        self,
        message: str,
        passages: list[Passage],
        screen: ScreenResult,
        abstained: bool,
        history: list[dict[str, str]],
    ) -> tuple[str, str]:
        if self.llm is not None and not abstained:
            user_prompt = build_user_prompt(
                message=message,
                passages=passages,
                flags=screen.flags,
                urgency_headline=screen.urgency.headline,
                urgency_actions=screen.urgency.actions,
                history=history,
            )
            try:
                text = self.llm.complete(
                    system=SYSTEM_PROMPT,
                    user=user_prompt,
                    max_tokens=700,
                )
                return text, f"llm:{self.llm.name}"
            except LLMError:
                fallback = compose(message, passages, screen, abstained=False)
                note = (
                    "\n\n_(Local model unavailable — this answer was composed directly from the evidence.)_"
                )
                return fallback + note, "extractive:llm-error"
        return compose(message, passages, screen, abstained), "extractive"
