from __future__ import annotations

import pytest

from symptompilot.safety.redflags import RedFlagEngine, normalise


@pytest.fixture(scope="module")
def engine() -> RedFlagEngine:
    return RedFlagEngine.from_yaml()


def test_normalise_expands_contractions_and_lowercases() -> None:
    assert normalise("I Can't Breathe") == "i cannot breathe"
    assert normalise("no   chest   pain") == "no chest pain"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("crushing chest pain going into my jaw", "emergency"),
        ("my face is drooping and speech is slurred", "emergency"),
        ("I am gasping for air", "emergency"),
        ("my throat is closing after peanuts", "emergency"),
        ("I want to die", "emergency"),
        ("I have a mild headache", "routine"),
        ("sore throat and runny nose", "routine"),
        ("I cannot keep fluids down", "urgent"),
        ("what is the capital of France", "unknown"),
    ],
)
def test_screen_levels(engine: RedFlagEngine, message: str, expected: str) -> None:
    assert engine.screen(message).urgency.level == expected


def test_negated_emergency_is_not_raised(engine: RedFlagEngine) -> None:
    result = engine.screen("no chest pain, just a runny nose")
    assert result.urgency.level == "routine"
    assert all(flag.id != "chest-pain" for flag in result.flags)


def test_conjunction_after_negation_keeps_emergency(engine: RedFlagEngine) -> None:
    result = engine.screen("no fever but I have crushing chest pain")
    assert result.urgency.level == "emergency"


def test_compound_rule_requires_all_parts(engine: RedFlagEngine) -> None:
    assert engine.screen("fever with a stiff neck").urgency.level == "emergency"
    assert engine.screen("stiff neck after sleeping badly").urgency.level != "emergency"


def test_emergency_takes_precedence_over_routine(engine: RedFlagEngine) -> None:
    result = engine.screen("mild headache but chest pressure and sweating")
    assert result.urgency.level == "emergency"
    levels = {flag.level for flag in result.flags}
    assert levels == {"emergency", "routine"}


def test_urgency_actions_present(engine: RedFlagEngine) -> None:
    urgency = engine.screen("severe difficulty breathing").urgency
    assert urgency.score == 100
    assert urgency.headline
    assert urgency.actions


def test_questions_for_matched_rules(engine: RedFlagEngine) -> None:
    screen = engine.screen("chest pain spreading to my arm")
    questions = engine.questions_for(screen.flags)
    assert questions
    assert all(isinstance(question, str) for question in questions)


def test_infant_fever_is_emergency(engine: RedFlagEngine) -> None:
    assert engine.screen("my baby has a fever").urgency.level == "emergency"
