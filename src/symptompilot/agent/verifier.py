"""Post-generation checks that keep answers tethered to retrieved evidence."""

from __future__ import annotations

import re

from symptompilot.models import Citation, Verification

_MARKER_RE = re.compile(r"\[S(\d+)\]")


def verify(answer: str, citations: list[Citation], urgency_level: str) -> tuple[str, Verification]:
    valid = {citation.marker for citation in citations}
    referenced = {f"S{match}" for match in _MARKER_RE.findall(answer)}
    invalid = sorted(referenced - valid)

    cleaned = answer
    for marker in invalid:
        cleaned = cleaned.replace(f"[{marker}]", "")

    notes: list[str] = []
    if invalid:
        notes.append(f"removed {len(invalid)} citation marker(s) with no matching evidence")
    if valid and not (referenced & valid):
        notes.append("answer contained no valid citation")
    if not citations:
        notes.append("no supporting evidence retrieved")
    if urgency_level == "emergency" and "emergency" not in cleaned.lower():
        notes.append("emergency escalation statement was added by the verifier")
        cleaned = "**Possible emergency — contact emergency services now.**\n\n" + cleaned

    return cleaned, Verification(
        cited_markers=sorted(referenced & valid, key=lambda m: int(m[1:])),
        invalid_markers=invalid,
        evidence_supplied=len(citations),
        notes=notes,
    )
