"""Deterministic red-flag screening.

This module deliberately has no model dependency: the escalation level a user
sees is produced by auditable rules, not by generated text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from symptompilot.models import Level_score, RedFlag, ScreenResult, Urgency

DEFAULT_RULES = Path(__file__).with_name("rules.yaml")

CONTRACTIONS = {
    "can't": "cannot",
    "cant": "cannot",
    "can not": "cannot",
    "won't": "will not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "hasn't": "has not",
    "haven't": "have not",
    "i'm": "i am",
    "i've": "i have",
    "it's": "it is",
    "that's": "that is",
    "can’t": "cannot",
    "won’t": "will not",
    "don’t": "do not",
    "doesn’t": "does not",
}

NEGATORS = {
    "no",
    "not",
    "without",
    "denies",
    "denied",
    "never",
    "negative",
    "free",
    "none",
}
CONJUNCTIONS = {"but", "however", "though", "except", "although", "just", "only", "apart"}
AMBIGUOUS = {"sure", "if", "whether", "know", "certain", "think"}


def normalise(text: str) -> str:
    lowered = text.replace("’", "'").replace("‘", "'").lower()
    for source, target in CONTRACTIONS.items():
        lowered = lowered.replace(source, target)
    lowered = re.sub(r"[^a-z0-9%.,!?'\-\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _is_negated(text: str, start: int) -> bool:
    window = text[max(0, start - 32) : start]
    tokens = window.split()
    tail = tokens[-3:]
    if any(token in CONJUNCTIONS for token in tail):
        return False
    hits = {token for token in tail if token in NEGATORS}
    if not hits:
        return False
    return not (hits == {"not"} and AMBIGUOUS & set(tokens))


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    level: str
    advice: str
    patterns: tuple[str, ...]
    all_of: tuple[str, ...]
    questions: tuple[str, ...]
    docs: tuple[str, ...] = ()

    def match(self, text: str) -> str | None:
        matched: str | None = None
        for pattern in self.patterns:
            for hit in re.finditer(pattern, text):
                if not _is_negated(text, hit.start()):
                    matched = hit.group(0)
                    break
            if matched:
                break
        if matched is None:
            return None
        for requirement in self.all_of:
            found = False
            for hit in re.finditer(requirement, text):
                if not _is_negated(text, hit.start()):
                    found = True
                    break
            if not found:
                return None
        return matched


class RedFlagEngine:
    """Loads ``rules.yaml`` and screens free text for warning signs."""

    def __init__(self, config: dict, source: str = "") -> None:
        self.levels: dict[str, dict] = config.get("levels", {})
        self.rules: list[Rule] = [
            Rule(
                id=str(item["id"]),
                label=str(item.get("label", item["id"])),
                level=str(item.get("level", "urgent")),
                advice=str(item.get("advice", "")).strip(),
                patterns=tuple(item.get("patterns") or ()),
                all_of=tuple(item.get("all_of") or ()),
                questions=tuple(item.get("questions") or ()),
                docs=tuple(item.get("docs") or ()),
            )
            for item in config.get("rules", [])
        ]
        self.source = source
        for rule in self.rules:
            for pattern in (*rule.patterns, *rule.all_of):
                re.compile(pattern)  # fail fast on invalid expressions

    @classmethod
    def from_yaml(cls, path: Path | str = DEFAULT_RULES) -> RedFlagEngine:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(data, source=str(path))

    def rule(self, rule_id: str) -> Rule | None:
        return next((rule for rule in self.rules if rule.id == rule_id), None)

    def screen(self, text: str) -> ScreenResult:
        normalised = normalise(text)
        flags: list[RedFlag] = []
        for rule in self.rules:
            matched = rule.match(normalised)
            if not matched:
                continue
            flags.append(
                RedFlag(
                    id=rule.id,
                    label=rule.label,
                    level=rule.level,  # type: ignore[arg-type]
                    advice=rule.advice,
                    matched_text=matched,
                )
            )

        level = "unknown" if not flags else max(flags, key=lambda flag: Level_score[flag.level]).level
        config = self.levels.get(level, {})
        urgency = Urgency(
            level=level,  # type: ignore[arg-type]
            score=int(config.get("score", Level_score[level])),
            headline=str(config.get("headline", "")),
            actions=[str(action) for action in config.get("actions", [])],
        )
        return ScreenResult(urgency=urgency, flags=flags)

    def questions_for(self, flags: list[RedFlag], limit: int = 3) -> list[str]:
        out: list[str] = []
        for flag in flags:
            rule = self.rule(flag.id)
            if not rule:
                continue
            for question in rule.questions:
                if question not in out:
                    out.append(question)
        return out[:limit]

    def preferred_docs(self, flags: list[RedFlag]) -> set[str]:
        """Knowledge-base pages most likely to explain the matched warning signs."""

        docs: set[str] = set()
        for flag in flags:
            rule = self.rule(flag.id)
            if rule:
                docs.update(rule.docs)
        return docs
