from __future__ import annotations

from symptompilot.agent.verifier import verify
from symptompilot.llm.base import LLMError
from symptompilot.models import Citation


class BoomClient:
    provider = "test"
    model = "boom"

    @property
    def name(self) -> str:
        return "test/boom"

    def available(self) -> bool:
        return True

    def complete(self, system: str, user: str, temperature: float = 0.1, max_tokens: int = 700) -> str:
        raise LLMError("model exploded")


class EchoClient(BoomClient):
    def complete(self, system: str, user: str, temperature: float = 0.1, max_tokens: int = 700) -> str:
        return "Possible emergency — contact emergency services now. Rest and monitor [S1]. Ignore [S9]."


def test_triage_answers_with_evidence(runtime) -> None:
    response = runtime.agent.triage("I have had a sore throat and runny nose for three days")
    assert response.citations
    assert response.urgency.level == "routine"
    assert response.mode == "extractive"
    assert "[S1]" in response.answer
    assert response.disclaimer


def test_triage_escalates_emergency(runtime) -> None:
    response = runtime.agent.triage("crushing chest pain and sweating")
    assert response.urgency.level == "emergency"
    assert "emergency" in response.answer.lower()
    assert response.red_flags


def test_triage_abstains_on_out_of_scope_question(runtime) -> None:
    response = runtime.agent.triage("What is the boiling point of water at sea level")
    assert response.abstained is True
    assert response.urgency.level == "unknown"
    assert response.citations == []


def test_triage_suggests_follow_ups(runtime) -> None:
    response = runtime.agent.triage("my stomach hurts")
    assert response.follow_up_questions
    assert len(response.follow_up_questions) <= 3


def test_llm_error_falls_back_to_extractive(runtime) -> None:
    from symptompilot.agent.orchestrator import TriageAgent

    agent = TriageAgent(
        retriever=runtime.retriever,
        engine=runtime.engine,
        settings=runtime.settings,
        llm=BoomClient(),
    )
    response = agent.triage("I have a mild headache")
    assert response.mode == "extractive:llm-error"
    assert response.answer


def test_llm_path_strips_invalid_citations(runtime) -> None:
    from symptompilot.agent.orchestrator import TriageAgent

    agent = TriageAgent(
        retriever=runtime.retriever,
        engine=runtime.engine,
        settings=runtime.settings,
        llm=EchoClient(),
    )
    response = agent.triage("I have a mild headache")
    assert response.mode.startswith("llm:")
    assert "[S9]" not in response.answer
    assert response.verification.invalid_markers == ["S9"]


def test_verify_adds_emergency_statement() -> None:
    citations = [Citation(marker="S1", doc_id="d", title="T", section="S", snippet="text", score=0.5)]
    cleaned, verification = verify("Rest and monitor how you feel [S1].", citations, "emergency")
    assert cleaned.lower().startswith("**possible emergency")
    assert any("emergency escalation statement" in note for note in verification.notes)
    assert verification.cited_markers == ["S1"]


def test_verify_removes_unknown_markers() -> None:
    citations = [Citation(marker="S1", doc_id="d", title="T", section="S", snippet="t", score=0.4)]
    cleaned, verification = verify("Rest [S1] and call [S7].", citations, "routine")
    assert "[S7]" not in cleaned
    assert verification.invalid_markers == ["S7"]
    assert verification.cited_markers == ["S1"]
