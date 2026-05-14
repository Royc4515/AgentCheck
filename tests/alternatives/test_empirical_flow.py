"""Tests for the empirical validation flow.

Verifies that AlternativesEngine(empirical=True) generates alternative agents,
calls CheckRunner (#1/#2/#3), and builds a FullComparisonReport from real
numbers rather than KB projections.

All LLM calls and check runs are mocked — this tests the orchestration logic,
not the underlying checks.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    AlternativesEngine,
    CheckRunner,
    DetectedPattern,
    FullComparisonReport,
    RecommendationType,
    ReliabilityResult,
    StubCheckRunner,
    ValidationStatus,
    WastefulnessResult,
    SecurityResult,
)
from agentcheck.alternatives.validation import LLMAgentGenerator


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def results_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".agentcheck"
    d.mkdir()
    _write(d / "reliability_result.json", {
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
    _write(d / "wastefulness_result.json", {
        "waste_score": 68.0,
        "cost_per_task_usd": 0.045,
        "baseline_cost_usd": 0.014,
    })
    _write(d / "security_result.json", {
        "is_safe": False,
        "critical_count": 1,
        "high_count": 2,
        "medium_count": 0,
        "low_count": 0,
        "finding_ids": ["S1", "S2", "S3"],
        "hardcoded_secrets": True,
        "prompt_injection_vulnerable": False,
        "unsafe_deserialization": False,
    })
    return d


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
def tasks_path(tmp_path: Path) -> Path:
    p = tmp_path / "tasks.yaml"
    p.write_text("tasks: []", encoding="utf-8")
    return p


@pytest.fixture()
def mock_generator(tmp_path: Path) -> LLMAgentGenerator:
    gen = MagicMock(spec=LLMAgentGenerator)
    agent_file = tmp_path / "alt_pydanticai_agent.py"
    agent_file.write_text("def run(user_input: str) -> str: return user_input", encoding="utf-8")
    gen.generate.return_value = agent_file
    return gen


# ---------------------------------------------------------------------------
# StubCheckRunner tests
# ---------------------------------------------------------------------------

class TestStubCheckRunner:
    def test_returns_reliability_result(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(task_completion_rate=0.85)
        result = runner.run_reliability(tmp_path / "agent.py", tmp_path / "tasks.yaml")
        assert result.task_completion_rate == pytest.approx(0.85)

    def test_returns_wastefulness_result(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(cost_per_task_usd=0.020)
        result = runner.run_wastefulness(tmp_path / "agent.py", tmp_path / "tasks.yaml")
        assert result.cost_per_task_usd == pytest.approx(0.020)

    def test_returns_security_result_clean(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(security_critical=0, security_high=0)
        result = runner.run_security(tmp_path / "agent.py")
        assert result.is_safe is True
        assert result.total_findings == 0

    def test_returns_security_result_with_findings(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(security_critical=1, security_high=1)
        result = runner.run_security(tmp_path / "agent.py")
        assert result.is_safe is False
        assert result.total_findings == 2


# ---------------------------------------------------------------------------
# Empirical mode end-to-end
# ---------------------------------------------------------------------------

class TestEmpiricalMode:
    def test_empirical_flag_triggers_check_runner(
        self,
        results_dir: Path,
        pydanticai_candidate: AlternativeCandidate,
        tasks_path: Path,
        mock_generator: LLMAgentGenerator,
    ) -> None:
        stub = StubCheckRunner(
            task_completion_rate=0.88,
            cost_per_task_usd=0.020,
        )
        engine = AlternativesEngine(
            results_dir=results_dir,
            candidates=[pydanticai_candidate],
            empirical=True,
            tasks_path=tasks_path,
            runner=stub,
        )
        engine._pipeline._generator = mock_generator

        report = engine.run()

        assert isinstance(report, FullComparisonReport)
        assert len(report.validation_results) == 1
        assert report.validation_results[0].status in (
            ValidationStatus.PASSED, ValidationStatus.FAILED
        )

    def test_empirical_comparison_uses_real_numbers_not_kb(
        self,
        results_dir: Path,
        pydanticai_candidate: AlternativeCandidate,
        tasks_path: Path,
        mock_generator: LLMAgentGenerator,
    ) -> None:
        # Runner returns 0.90 reliability — different from KB's 0.81
        stub = StubCheckRunner(task_completion_rate=0.90, cost_per_task_usd=0.015)
        engine = AlternativesEngine(
            results_dir=results_dir,
            candidates=[pydanticai_candidate],
            empirical=True,
            tasks_path=tasks_path,
            runner=stub,
        )
        engine._pipeline._generator = mock_generator
        report = engine.run()

        comp = report.comparisons[0]
        # alt_reliability must come from runner (0.90), not KB (0.81)
        assert comp.alt_reliability == pytest.approx(0.90)
        assert comp.alt_cost == pytest.approx(0.015)

    def test_empirical_validation_passed_when_alternative_wins(
        self,
        results_dir: Path,
        pydanticai_candidate: AlternativeCandidate,
        tasks_path: Path,
        mock_generator: LLMAgentGenerator,
    ) -> None:
        # Original: 72% reliability, $0.045/task, 3 security findings
        # Alternative: 85% reliability (+13pp ✓), $0.020/task (-56% ✓), 0 findings ✓
        stub = StubCheckRunner(
            task_completion_rate=0.85,
            cost_per_task_usd=0.020,
            security_critical=0,
            security_high=0,
        )
        engine = AlternativesEngine(
            results_dir=results_dir,
            candidates=[pydanticai_candidate],
            empirical=True,
            tasks_path=tasks_path,
            runner=stub,
        )
        engine._pipeline._generator = mock_generator
        report = engine.run()

        vr = report.validation_results[0]
        assert vr.status == ValidationStatus.PASSED
        assert vr.confirmed_dominates is True

    def test_empirical_validation_failed_on_reliability_regression(
        self,
        results_dir: Path,
        pydanticai_candidate: AlternativeCandidate,
        tasks_path: Path,
        mock_generator: LLMAgentGenerator,
    ) -> None:
        # Original: 72% reliability. Alternative crashes to 50% → -31% → blocked
        stub = StubCheckRunner(task_completion_rate=0.50, cost_per_task_usd=0.010)
        engine = AlternativesEngine(
            results_dir=results_dir,
            candidates=[pydanticai_candidate],
            empirical=True,
            tasks_path=tasks_path,
            runner=stub,
        )
        engine._pipeline._generator = mock_generator
        report = engine.run()

        vr = report.validation_results[0]
        assert vr.status == ValidationStatus.FAILED
        assert vr.confirmed_dominates is False

    def test_empirical_requires_tasks_path(
        self,
        results_dir: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = AlternativesEngine(
            results_dir=results_dir,
            candidates=[pydanticai_candidate],
            empirical=True,
            tasks_path=None,  # missing — must raise
        )
        with pytest.raises(ValueError, match="tasks_path"):
            engine.run()

    def test_kb_mode_has_no_validation_results(
        self,
        results_dir: Path,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = AlternativesEngine(
            results_dir=results_dir,
            candidates=[pydanticai_candidate],
            empirical=False,
        )
        report = engine.run()
        assert report.validation_results == []
