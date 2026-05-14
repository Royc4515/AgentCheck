"""Test #2 — Framework Shift: LangChain → PydanticAI."""

import pytest

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    DetectedPattern,
    MatchingEngine,
    RecommendationType,
    ReliabilityResult,
    WastefulnessResult,
)


@pytest.fixture()
def langchain_profile() -> AgentProfile:
    return AgentProfile(
        framework="langchain",
        framework_confidence=0.94,
        model_id="gpt-4o",
        detected_patterns=[DetectedPattern.STRUCTURED_EXTRACTION],
        reliability=ReliabilityResult(
            task_completion_rate=0.72,
            tasks_passed=7,
            tasks_total=10,
            framework="langchain",
            framework_confidence=0.94,
            model_id="gpt-4o",
            detected_patterns=["structured_extraction"],
            loc=180,
            cyclomatic_complexity=24,
        ),
        wastefulness=WastefulnessResult(
            waste_score=58.0,
            cost_per_task_usd=0.045,
            baseline_cost_usd=0.017,
        ),
    )


@pytest.fixture()
def pydanticai_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="pydanticai",
        name="PydanticAI",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="Type-safe, minimal framework with first-class structured outputs.",
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
def langchain_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="langchain",
        name="LangChain",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        description="The agent's current framework.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.72,
            cost_per_task_usd=0.045,
            loc_estimate=180,
            cyclomatic_complexity=24,
            security_finding_count=0,
        ),
        freshness_score=1.0,
    )


class TestFrameworkShift:
    def test_pydanticai_dominates_langchain(
        self,
        langchain_profile: AgentProfile,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[pydanticai_candidate])
        ranked = engine.rank(langchain_profile)

        assert len(ranked) == 1
        assert ranked[0].id == "pydanticai"
        assert ranked[0].dominance is not None
        assert ranked[0].dominance.dominates is True

    def test_complexity_reduction_meets_threshold(
        self,
        langchain_profile: AgentProfile,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[pydanticai_candidate])
        ranked = engine.rank(langchain_profile)

        dominance = ranked[0].dominance
        assert "complexity" in dominance.winning_axes
        # 180 → 90 = 50 % reduction, clears ≥ 40 %
        assert dominance.complexity_delta_pct is not None
        assert dominance.complexity_delta_pct >= 40.0

    def test_same_framework_not_recommended(
        self,
        langchain_profile: AgentProfile,
        langchain_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[langchain_candidate])
        ranked = engine.rank(langchain_profile)

        assert ranked == []

    def test_pydanticai_ranked_above_langchain_when_both_present(
        self,
        langchain_profile: AgentProfile,
        pydanticai_candidate: AlternativeCandidate,
        langchain_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[langchain_candidate, pydanticai_candidate])
        ranked = engine.rank(langchain_profile)

        ids = [c.id for c in ranked]
        assert "langchain" not in ids
        assert "pydanticai" in ids

    def test_cost_also_improves(
        self,
        langchain_profile: AgentProfile,
        pydanticai_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[pydanticai_candidate])
        ranked = engine.rank(langchain_profile)

        # $0.045 → $0.028 = 37.8 % reduction, clears ≥ 30 %
        assert "cost" in ranked[0].dominance.winning_axes
