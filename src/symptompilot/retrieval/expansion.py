"""Lay-vocabulary expansion.

People describe symptoms with everyday words ("pee", "hurts", "tummy") while
clinical reference text uses different ones ("urine", "pain", "abdomen"). Each
query token becomes a *concept group*: the token plus known equivalents. A
document satisfies the concept if it contains any variant.
"""

from __future__ import annotations

from symptompilot.retrieval.bm25 import tokenize

SYNONYMS: dict[str, tuple[str, ...]] = {
    "pee": ("urine", "urinary", "urinate", "void"),
    "peeing": ("pee", "urine", "urinate"),
    "peed": ("pee", "urine", "urinate"),
    "urinate": ("urine", "urinary", "pee"),
    "urination": ("urine", "urinary", "urinate"),
    "burn": ("burning", "sting", "pain"),
    "burns": ("burn", "burning", "sting"),
    "burning": ("burn", "sting", "pain"),
    "hurt": ("pain", "ache", "painful"),
    "hurts": ("hurt", "pain", "ache"),
    "aching": ("ache", "pain"),
    "tummy": ("abdomen", "abdominal", "stomach", "belly"),
    "belly": ("abdomen", "abdominal", "stomach"),
    "poop": ("stool", "bowel"),
    "pooing": ("stool", "bowel"),
    "vomit": ("vomiting", "nausea", "throwing"),
    "puke": ("vomit", "nausea"),
    "dizzy": ("dizziness", "lightheaded", "faint"),
    "dizziness": ("dizzy", "lightheaded"),
    "breathless": ("breathing", "breath", "shortness"),
    "breathlessness": ("breathing", "breath", "shortness"),
    "breathing": ("breath", "breathless", "shortness"),
    "feverish": ("fever", "temperature"),
    "temperature": ("fever", "hot"),
    "chills": ("fever", "shivering"),
    "die": ("suicide", "suicidal", "death", "self"),
    "dying": ("die", "suicide", "suicidal"),
    "suicide": ("suicidal", "self", "die"),
    "suicidal": ("suicide", "self", "die"),
    "sleep": ("insomnia", "sleeping"),
    "insomnia": ("sleep", "sleeping"),
    "palpitations": ("heart", "pulse", "racing"),
    "heartbeat": ("heart", "pulse", "palpitations"),
    "swollen": ("swelling", "swell"),
    "swelling": ("swollen", "swell"),
    "numb": ("numbness", "tingling"),
    "numbness": ("numb", "tingling"),
    "weak": ("weakness", "strength"),
    "weakness": ("weak", "strength"),
    "seizure": ("convulsion", "fit"),
    "seizures": ("seizure", "convulsion"),
    "faint": ("fainting", "passed", "collapse"),
    "fainted": ("faint", "passed", "collapse"),
    "headache": ("head", "migraine"),
    "migraine": ("headache", "head"),
    "throat": ("swallow", "swallowing"),
    "rash": ("hives", "skin"),
}


def concept_groups(text: str) -> list[tuple[str, ...]]:
    """Return one concept group per distinct query token, in order."""

    groups: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for token in tokenize(text):
        if token in seen:
            continue
        seen.add(token)
        variants = SYNONYMS.get(token, ())
        group = (token, *[variant for variant in variants if variant != token and variant not in seen])
        groups.append(group)
    return groups


def flatten(groups: list[tuple[str, ...]]) -> list[str]:
    return [token for group in groups for token in group]
