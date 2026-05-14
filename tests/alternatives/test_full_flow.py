"""End-to-end flow test: JSON files → AgentProfile → top 3 → FullComparisonReport."""

import json
import pytest
from pathlib import Path

from agentcheck.alternatives import (
    AlternativeCandidate,
    AlternativeMetrics,
    AlternativesEngine,
    DetectedPattern,
    FullComparisonReport,
    RecommendationType,
)


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def results_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".agentcheck"
    d.mkdir()
    return d


@pytest.fixture()
def langchain_results(results_dir: Path) -> Path:
    """Simulate a LangChain agent that's wasteful and has security issues."""
    _write(results_dir / "reliability_result.json", {
        "task_completion_rate": 0.72,
        "tasks_passed": 7,
        "tasks_total": 10,
        "framework": "langchain",
        "framework_confidence": 0.94,
        "model_id": "gpt-4o",
        "detected_patterns": ["react_loop"],
        "loc": 180,
        "cyclomatic_complexity": 24,
    })
    _write(results_dir / "wastefulness_result.json", {
        "waste_score": 70.0,
        "cost_per_task_usd": 0.045,
        "baseline_cost_usd": 0.014,
        "token_bloat_pct": 45.0,
        "model_over_spec": True,
        "suggested_model": "gpt-4o-mini",
        "redundant_tool_calls": 3,
        "retry_storms_detected": 1,
        "has_parallelizable_calls": True,
    })
    _write(results_dir / "security_result.json", {
        "is_safe": False,
        "critical_count": 1,
        "high_count": 1,
        "medium_count": 2,
        "low_count": 1,
        "finding_ids": ["S1", "S2", "S3", "S4", "S5"],
        "hardcoded_secrets": True,
        "prompt_injection_vulnerable": False,
        "unsafe_deserialization": False,
    })
    return results_dir


@pytest.fixture()
def pydanticai_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="pydanticai",
        name="PydanticAI",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="Minimal, type-safe framework.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.81,
            cost_per_task_usd=0.028,
            loc_estimate=90,
            cyclomatic_complexity=11,
            security_finding_count=0,
        ),
        freshness_score=1.0,
    )


@pytest.fixture()
def raw_sdk_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="raw_sdk",
        name="Raw SDK",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="Zero abstraction tax.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.85,
            cost_per_task_usd=0.021,
            loc_estimate=75,
            cyclomatic_complexity=9,
            security_finding_count=0,
        ),
        freshness_score=1.0,
    )


@pytest.fixture()
def model_downgrade_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="model_downgrade",
        name="Model Downgrade (gpt-4o-mini)",
        recommendation_type=RecommendationType.MODEL_DOWNGRADE,
        description="Swap to a cheaper model.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.74,
            cost_per_task_usd=0.012,
            loc_estimate=180,
            cyclomatic_complexity=24,
            security_finding_count=5,
        ),
        freshness_score=1.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFullFlow:
    def test_report_is_full_comparison_report(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[pydanticai_candidate],
        )
        report = engine.run()

        assert isinstance(report, FullComparisonReport)

    def test_profile_populated_from_json(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[pydanticai_candidate],
        )
        report = engine.run()

        assert report.agent_profile.framework == "langchain"
        assert report.agent_profile.task_completion_rate == pytest.approx(0.72)
        assert report.agent_profile.cost_per_task_usd == pytest.approx(0.045)
        assert report.agent_profile.security_finding_count == 5

    def test_top3_never_exceeds_three(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
        raw_sdk_candidate: AlternativeCandidate,
        model_downgrade_candidate: AlternativeCandidate,
    ) -> None:
        # Give it 3+ candidates
        extra = AlternativeCandidate(
            id="autogen",
            name="AutoGen",
            recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
            description="Multi-agent framework.",
            kb_metrics=AlternativeMetrics(
                reliability_score=0.74,
                cost_per_task_usd=0.030,
                loc_estimate=140,
                cyclomatic_complexity=19,
                security_finding_count=0,
            ),
            freshness_score=1.0,
        )
        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[
                pydanticai_candidate,
                raw_sdk_candidate,
                model_downgrade_candidate,
                extra,
            ],
        )
        report = engine.run()

        assert len(report.comparisons) <= 3

    def test_comparison_contains_original_and_alt_values(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[pydanticai_candidate],
        )
        report = engine.run()
        comp = report.comparisons[0]

        # Original values come from JSON
        assert comp.original_reliability == pytest.approx(0.72)
        assert comp.original_cost == pytest.approx(0.045)
        assert comp.original_loc == 180
        assert comp.original_security_findings == 5

        # Alt values come from KB
        assert comp.alt_reliability == pytest.approx(0.81)
        assert comp.alt_cost == pytest.approx(0.028)
        assert comp.alt_loc == 90
        assert comp.alt_security_findings == 0

    def test_security_winning_axis_included(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        """PydanticAI has 0 security findings vs 5 in original → security should win."""
        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[pydanticai_candidate],
        )
        report = engine.run()
        dominance = report.comparisons[0].candidate.dominance

        assert dominance is not None
        assert "security" in dominance.winning_axes

    def test_no_results_dir_returns_empty_profile(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        engine = AlternativesEngine(results_dir=empty_dir, candidates=[])
        report = engine.run()

        assert report.agent_profile.framework is None
        assert report.comparisons == []

    def test_top_recommendation_property(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[pydanticai_candidate],
        )
        report = engine.run()

        top = report.top_recommendation
        assert top is not None
        assert top.id == "pydanticai"

    def test_reporter_summary_mode(
        self,
        langchain_results: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        from agentcheck.alternatives import AlternativesReporter

        engine = AlternativesEngine(
            results_dir=langchain_results,
            candidates=[pydanticai_candidate],
        )
        report = engine.run()
        summary = AlternativesReporter(mode="summary").render(report)

        assert "PydanticAI" in summary
        assert "AgentCheck v0.4" in summary
