"""Prompts for the grounded answer generator."""

from __future__ import annotations

from symptompilot.models import Passage, RedFlag

SYSTEM_PROMPT = """You are SymptomPilot, an educational triage assistant.

Absolute rules:
1. You are not a clinician. Never give a diagnosis, never say a condition is ruled out,
   never give drug names with doses, and never tell someone to stop prescribed treatment.
2. Use ONLY the numbered evidence blocks provided. Cite every clinical statement with its
   marker, for example [S1]. Never invent a marker that is not in the evidence list.
3. If the evidence does not cover the question, say so plainly in one sentence and advise
   seeing a clinician. Do not fill gaps with general knowledge about diseases.
4. The urgency level is decided by a deterministic safety engine, not by you. Repeat it in
   your first sentence and never downgrade or contradict it.
5. Be calm and concrete. Plain language, short paragraphs, no more than 220 words.
6. No dosages, no prescriptions, no "I think you have". Use "can be associated with" or
   "possible explanations include".

Answer format:
- First line: the urgency statement given under "Urgency".
- "What may help now": 2-3 practical, low-risk steps drawn from the evidence.
- "When to get more help": signs that mean escalating care, drawn from the evidence.
- Cite sources inline as [S1], [S2] etc."""


def evidence_block(passages: list[Passage]) -> str:
    lines: list[str] = []
    for index, passage in enumerate(passages, start=1):
        body = " ".join(passage.text.split())
        lines.append(f"[S{index}] {passage.title} — {passage.section}\n{body}")
    return "\n\n".join(lines) if lines else "(no evidence retrieved)"


def format_history(history: list[dict[str, str]], limit: int = 6) -> str:
    turns = []
    for item in history[-limit:]:
        role = item.get("role", "")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            speaker = "Patient" if role == "user" else "Assistant"
            turns.append(f"{speaker}: {content[:600]}")
    return "\n".join(turns)


def build_user_prompt(
    message: str,
    passages: list[Passage],
    flags: list[RedFlag],
    urgency_headline: str,
    urgency_actions: list[str],
    history: list[dict[str, str]] | None = None,
) -> str:
    flag_text = ", ".join(f"{flag.label} ({flag.level})" for flag in flags) or "none detected"
    actions = "\n".join(f"- {action}" for action in urgency_actions) or "- none"
    history_text = format_history(history or [])
    return f"""Urgency: {urgency_headline}
Red flags detected by the safety engine: {flag_text}
Urgency actions to include or respect:
{actions}

Conversation so far (may be empty):
{history_text or "(new conversation)"}

Patient message:
{message}

Evidence:
{evidence_block(passages)}
"""
