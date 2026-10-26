"""Deterministic answer composition used when no LLM is available.

Answers stay grounded because every clinical sentence is copied from a retrieved
knowledge-base passage and carries its marker.
"""

from __future__ import annotations

import re

from symptompilot.models import Passage, ScreenResult
from symptompilot.retrieval.bm25 import tokenize

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(" ".join(text.split())) if len(s.strip()) > 25]


def _rank_sentences(text: str, query_tokens: list[str], limit: int) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        return []
    query = set(query_tokens)
    scored = []
    for position, sentence in enumerate(sentences):
        overlap = len(query & set(tokenize(sentence)))
        scored.append((overlap, -position, sentence))
    scored.sort(reverse=True)
    chosen = [item[2] for item in scored[:limit] if item[0] > 0] or [sentences[0]]
    chosen.sort(key=lambda s: sentences.index(s))
    return chosen


def compose(
    message: str,
    passages: list[Passage],
    screen: ScreenResult,
    abstained: bool,
) -> str:
    urgency = screen.urgency
    query_tokens = tokenize(message)
    lines: list[str] = [f"**{urgency.headline}.**"]

    if screen.flags:
        labels = ", ".join(dict.fromkeys(flag.label.lower() for flag in screen.flags))
        lines.append(f"Signals recognised in your message: {labels}.")
        if screen.flags[0].advice:
            lines.append(screen.flags[0].advice)

    if abstained or not passages:
        lines.append(
            "I could not find guidance in the knowledge base that clearly matches this question, "
            "so I will not guess. The safest next step is to describe the symptom to a clinician "
            "or a nurse advice line."
        )
    else:
        lines.append("")
        lines.append("**What the guidance says**")
        for index, passage in enumerate(passages[:3], start=1):
            picked = _rank_sentences(passage.text, query_tokens, limit=2)
            if not picked:
                continue
            lines.append(f"- {' '.join(picked)} [S{index}]")

    if urgency.actions:
        lines.append("")
        lines.append("**What may help now**")
        for action in urgency.actions[:3]:
            lines.append(f"- {action}")

    lines.append("")
    lines.append("**When to get help sooner**")
    if urgency.level == "emergency":
        lines.append("- Do not wait for symptoms to settle on their own; call emergency services now.")
    elif urgency.level == "urgent":
        lines.append("- If symptoms worsen today, go to an emergency department rather than waiting.")
    else:
        lines.append(
            "- If fever, breathlessness, chest pain, fainting or confusion appear, seek urgent care."
        )
    lines.append("- If you are worried, it is always reasonable to speak to a clinician.")

    sources = list(passages[:3])
    if sources:
        lines.append("")
        lines.append("**Evidence used**")
        for index, passage in enumerate(sources, start=1):
            publisher = passage.sources[0].publisher if passage.sources else ""
            suffix = f" — {publisher}" if publisher else ""
            lines.append(f"- [S{index}] {passage.title} › {passage.section}{suffix}")

    return "\n".join(lines).strip()
