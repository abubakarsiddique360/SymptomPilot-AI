from __future__ import annotations

from symptompilot.evaluation.runner import THRESHOLDS, load_cases, run_evaluation


def test_cases_file_is_well_formed() -> None:
    cases = load_cases()
    assert len(cases) >= 15
    for case in cases:
        assert {"id", "message", "expect_level"} <= set(case)
        assert case["expect_level"] in {"emergency", "urgent", "routine", "unknown"}


def test_evaluation_meets_thresholds(runtime) -> None:
    report = run_evaluation(runtime.agent)
    assert report.metrics["level_accuracy"] >= THRESHOLDS["level_accuracy"], report.summary()
    assert report.metrics["retrieval_hit_rate"] >= THRESHOLDS["retrieval_hit_rate"], report.summary()
    assert report.metrics["emergency_recall"] >= THRESHOLDS["emergency_recall"], report.summary()
    assert report.passed


def test_report_is_serialisable(runtime) -> None:
    report = run_evaluation(runtime.agent)
    payload = report.to_dict()
    assert payload["passed"] is True
    assert payload["metrics"]["emergency_recall"] == 1.0
    assert isinstance(report.summary(), str)
