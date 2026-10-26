"""Offline evaluation harness.

Two things are measured separately on purpose:

* red-flag screening — did the deterministic engine choose the right urgency?
* retrieval — did the right knowledge-base page reach the top results?

Keeping them apart means a regression in safety shows up independently of a
regression in search quality.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from symptompilot.agent.orchestrator import TriageAgent

DEFAULT_CASES = Path(__file__).with_name("cases.yaml")
THRESHOLDS = {"level_accuracy": 0.9, "retrieval_hit_rate": 0.8, "emergency_recall": 1.0}


@dataclass
class CaseResult:
    id: str
    message: str
    expected_level: str
    predicted_level: str
    level_ok: bool
    expected_docs: list[str]
    retrieved_docs: list[str]
    retrieval_ok: bool | None
    abstained: bool | None
    abstain_ok: bool | None
    latency_ms: int


@dataclass
class EvalReport:
    metrics: dict[str, float] = field(default_factory=dict)
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(self.metrics.get(key, 0.0) >= value for key, value in THRESHOLDS.items())

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "thresholds": THRESHOLDS,
            "metrics": self.metrics,
            "cases": [asdict(case) for case in self.cases],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def summary(self) -> str:
        rows = ["metric                     value", "------------------------   -----"]
        rows += [f"{key:<25} {value:>5.2f}" for key, value in self.metrics.items()]
        rows.append("")
        rows.append(f"{'case':<26}{'expected':<11}{'predicted':<11}{'retrieval':<10}ok")
        rows.append("-" * 68)
        for case in self.cases:
            retrieval = "n/a" if case.retrieval_ok is None else ("hit" if case.retrieval_ok else "miss")
            rows.append(
                f"{case.id:<26}{case.expected_level:<11}{case.predicted_level:<11}"
                f"{retrieval:<10}{'yes' if case.level_ok else 'no'}"
            )
        rows.append("")
        rows.append("PASSED" if self.passed else "FAILED")
        return "\n".join(rows)


def load_cases(path: Path | str = DEFAULT_CASES) -> list[dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return list(data.get("cases") or [])


def run_evaluation(
    agent: TriageAgent,
    cases_path: Path | str = DEFAULT_CASES,
    top_k: int = 3,
) -> EvalReport:
    cases = load_cases(cases_path)
    results: list[CaseResult] = []
    for case in cases:
        response = agent.triage(case["message"], top_k=top_k)
        retrieved = list(dict.fromkeys(citation.doc_id for citation in response.citations))
        expected_docs = list(case.get("expect_docs") or [])
        retrieval_ok = None
        if expected_docs:
            retrieval_ok = any(doc in retrieved for doc in expected_docs)
        expect_abstain = case.get("expect_abstain")
        results.append(
            CaseResult(
                id=str(case["id"]),
                message=str(case["message"]),
                expected_level=str(case["expect_level"]),
                predicted_level=response.urgency.level,
                level_ok=response.urgency.level == case["expect_level"],
                expected_docs=expected_docs,
                retrieved_docs=retrieved,
                retrieval_ok=retrieval_ok,
                abstained=response.abstained if expect_abstain is not None else None,
                abstain_ok=(response.abstained == expect_abstain) if expect_abstain is not None else None,
                latency_ms=response.latency_ms,
            )
        )

    level_scores = [1.0 if case.level_ok else 0.0 for case in results]
    retrieval_scores = [
        1.0 if case.retrieval_ok else 0.0 for case in results if case.retrieval_ok is not None
    ]
    emergency_cases = [case for case in results if case.expected_level == "emergency"]
    emergency_hits = [1.0 if case.predicted_level == "emergency" else 0.0 for case in emergency_cases]
    abstain_cases = [case for case in results if case.abstain_ok is not None]

    metrics = {
        "level_accuracy": round(sum(level_scores) / len(level_scores), 3) if level_scores else 0.0,
        "retrieval_hit_rate": round(sum(retrieval_scores) / len(retrieval_scores), 3)
        if retrieval_scores
        else 0.0,
        "emergency_recall": round(sum(emergency_hits) / len(emergency_hits), 3) if emergency_hits else 1.0,
        "abstain_accuracy": round(
            sum(1.0 if case.abstain_ok else 0.0 for case in abstain_cases) / len(abstain_cases), 3
        )
        if abstain_cases
        else 1.0,
    }
    return EvalReport(metrics=metrics, cases=results)
