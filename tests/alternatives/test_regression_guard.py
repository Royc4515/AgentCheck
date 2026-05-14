"""Test #3 — The Regression Guard."""

import pytest
from pathlib import Path

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    DetectedPattern,
    MatchingEngine,
    RecommendationType,
    ReliabilityResult,
    StubCheckRunner,
    WastefulnessResult,
)
from agentcheck.alternatives.matching_engine import DominanceChecker


@pytest.fixture()
def reliable_agent_profile() -> AgentProfile:
    return AgentProfile(
        framework="langchain",
        framework_confidence=0.90,
        model_id="claude-sonnet-4-6",
        detected_patterns=[DetectedPattern.REACT_LOOP],
        reliability=ReliabilityResult(
            task_completion_rate=0.80,
            tasks_passed=8,
            tasks_total=10,
            framework="langchain",
            loc=160,
            cyclomatic_complexity=20,
        ),
        wastefulness=WastefulnessResult(
            waste_score=40.0,
            cost_per_task_usd=0.050,
            baseline_cost_usd=0.020,
        ),
    )


@pytest.fixture()
def cheap_but_unreliable_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="cheap_framework",
        name="Cheap Framework",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="Super cheap but fails a lot of tasks.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.55,   # -31.25 % from 0.80 — hard regression
            cost_per_task_usd=0.010,  # 80 % cheaper
            loc_estimate=60,
            cyclomatic_complexity=8,
            security_finding_count=0,
        ),
        freshness_score=1.0,
    )


@pytest.fixture()
def borderline_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="borderline_framework",
        name="Borderline Framework",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="Sits right at the regression boundary.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.68,   # 0.80 * (1 - 0.15) = 0.68 exactly
            cost_per_task_usd=0.010,
            loc_estimate=60,
            cyclomatic_complexity=8,
            security_finding_count=0,
        ),
        freshness_score=1.0,
    )


@pytest.fixture()
def just_safe_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="just_safe_framework",
        name="Just-Safe Framework",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="Barely inside the regression guard.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.681,  # 14.9 % regression — inside guard
            cost_per_task_usd=0.010,  # 80 % cost improvement
            loc_estimate=60,
            cyclomatic_complexity=8,
            security_finding_count=0,
        ),
        freshness_score=1.0,
    )


class TestRegressionGuard:
    def test_hard_regression_blocked(
        self,
        reliable_agent_profile: AgentProfile,
        cheap_but_unreliable_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[cheap_but_unreliable_candidate])
        ranked = engine.rank(reliable_agent_profile)

        assert len(ranked) == 1
        dominance = ranked[0].dominance
        assert dominance.dominates is False
        assert "reliability" in dominance.regressed_axes

    def test_exact_15pct_regression_blocked(
        self,
        reliable_agent_profile: AgentProfile,
        borderline_candidate: AlternativeCandidate,
    ) -> None:
        checker = DominanceChecker()
        result = checker.check(reliable_agent_profile, borderline_candidate)

        # (0.68 - 0.80) / 0.80 = -0.15 → exactly -15 %
        assert result.reliability_delta_pct is not None
        assert abs(result.reliability_delta_pct - (-15.0)) < 0.5

    def test_just_inside_guard_allowed_when_cost_wins(
        self,
        reliable_agent_profile: AgentProfile,
        just_safe_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[just_safe_candidate])
        ranked = engine.rank(reliable_agent_profile)

        assert len(ranked) == 1
        dominance = ranked[0].dominance
        assert "reliability" not in dominance.regressed_axes
        assert "cost" in dominance.winning_axes
        assert dominance.dominates is True

