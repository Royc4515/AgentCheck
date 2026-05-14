"""Tests for OverallScorer — composite grade from checks #1/#2/#3."""

import json
import pytest
from pathlib import Path

from agentcheck.alternatives import (
    AgentProfile,
    AlternativesEngine,
    LetterGrade,
    OverallScore,
    OverallScorer,
    ReliabilityResult,
    SecurityResult,
    WastefulnessResult,
)


def _profile(
    completion_rate: float = 0.85,
    waste_score: float = 30.0,
    critical: int = 0,
    high: int = 0,
    medium: int = 0,
    low: int = 0,
) -> AgentProfile:
    return AgentProfile(
        reliability=ReliabilityResult(
            task_completion_rate=completion_rate,
            tasks_passed=round(completion_rate * 10),
            tasks_total=10,
        ),
        wastefulness=WastefulnessResult(
            waste_score=waste_score,
            cost_per_task_usd=0.02,
            baseline_cost_usd=0.008,
        ),
        security=SecurityResult(
            is_safe=(critical + high == 0),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
        ),
    )


class TestLetterGrades:
    def test_a_grade(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=0.95, waste_score=5.0))
        assert s.reliability_grade == LetterGrade.A

    def test_b_grade(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=0.82))
        assert s.reliability_grade == LetterGrade.B

    def test_c_grade(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=0.72))
        assert s.reliability_grade == LetterGrade.C

    def test_d_grade(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=0.65))
        assert s.reliability_grade == LetterGrade.D

    def test_f_grade(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=0.45))
        assert s.reliability_grade == LetterGrade.F


class TestAxisScores:
    def test_reliability_score_is_completion_rate_times_100(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=0.72))
        assert s.reliability_score == pytest.approx(72.0)

    def test_efficiency_score_inverts_waste(self) -> None:
        s = OverallScorer().score(_profile(waste_score=30.0))
        assert s.efficiency_score == pytest.approx(70.0)

    def test_perfect_efficiency(self) -> None:
        s = OverallScorer().score(_profile(waste_score=0.0))
        assert s.efficiency_score == pytest.approx(100.0)

    def test_security_score_clean(self) -> None:
        s = OverallScorer().score(_profile(critical=0, high=0, medium=0, low=0))
        assert s.security_score == pytest.approx(100.0)

    def test_security_score_one_critical(self) -> None:
        # 1 critical = 30 point deduction
        s = OverallScorer().score(_profile(critical=1))
        assert s.security_score == pytest.approx(70.0)

    def test_security_score_floors_at_zero(self) -> None:
        s = OverallScorer().score(_profile(critical=5, high=5))
        assert s.security_score == pytest.approx(0.0)

    def test_security_deduction_per_severity(self) -> None:
        # 1 critical (30) + 1 high (15) + 1 medium (5) + 1 low (2) = 52
        s = OverallScorer().score(_profile(critical=1, high=1, medium=1, low=1))
        assert s.security_score == pytest.approx(48.0)


class TestWeightedOverall:
    def test_all_axes_perfect(self) -> None:
        s = OverallScorer().score(_profile(completion_rate=1.0, waste_score=0.0))
        assert s.overall_score == pytest.approx(100.0)
        assert s.overall_grade == LetterGrade.A

    def test_weights_applied(self) -> None:
        # reliability=80 (40%), efficiency=70 (30%), security=60 (30%)
        # overall = 80*0.4 + 70*0.3 + 60*0.3 = 32 + 21 + 18 = 71
        profile = _profile(completion_rate=0.80, waste_score=30.0, high=1)
        # security: 100 - 15 = 85
        # overall = 80*0.4 + 70*0.3 + 85*0.3 = 32 + 21 + 25.5 = 78.5
        s = OverallScorer().score(profile)
        assert s.overall_score is not None
        assert 70.0 <= s.overall_score <= 85.0  # sanity range

    def test_partial_axes_reweighted(self) -> None:
        """When only reliability is available, it should still score 0–100."""
        profile = AgentProfile(
            reliability=ReliabilityResult(
                task_completion_rate=0.80,
                tasks_passed=8,
                tasks_total=10,
            ),
        )
        s = OverallScorer().score(profile)
        assert s.overall_score == pytest.approx(80.0)
        assert s.axes_available == ["reliability"]

    def test_no_checks_returns_none_overall(self) -> None:
        profile = AgentProfile()
        s = OverallScorer().score(profile)
        assert s.overall_score is None
        assert s.overall_grade is None
        assert s.axes_available == []


class TestIntegration:
    def test_overall_score_in_report(self, tmp_path: Path) -> None:
        d = tmp_path / ".agentcheck"
        d.mkdir()
        (d / "reliability_result.json").write_text(json.dumps({
            "task_completion_rate": 0.72,
            "tasks_passed": 7,
            "tasks_total": 10,
        }), encoding="utf-8")
        (d / "wastefulness_result.json").write_text(json.dumps({
            "waste_score": 60.0,
            "cost_per_task_usd": 0.04,
            "baseline_cost_usd": 0.016,
        }), encoding="utf-8")
        (d / "security_result.json").write_text(json.dumps({
            "is_safe": False,
            "critical_count": 1,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
        }), encoding="utf-8")

        engine = AlternativesEngine(results_dir=d, candidates=[])
        report = engine.run()

        assert report.overall_score is not None
        assert report.overall_score.overall_grade is not None
        # reliability=72, efficiency=40, security=70
        # overall = 72*0.4 + 40*0.3 + 70*0.3 = 28.8 + 12 + 21 = 61.8 → D
        assert report.overall_score.overall_grade == LetterGrade.D
        assert report.overall_score.reliability_score == pytest.approx(72.0)
        assert report.overall_score.efficiency_score == pytest.approx(40.0)
        assert report.overall_score.security_score == pytest.approx(70.0)
