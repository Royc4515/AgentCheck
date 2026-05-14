"""Test #2 — Framework Shift: LangChain → PydanticAI.

Scenario: a heavy LangChain agent with 180 LOC performing a simple
structured extraction task.  PydanticAI accomplishes the same task in ~90
LOC (50 % reduction, which clears the ≥40 % complexity threshold) at lower
cost and higher reliability.  The MatchingEngine must:
  - Rank PydanticAI above LangChain
  - Report that complexity and reliability both win
  - Not recommend LangChain to itself
"""

import pytest

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    DetectedPattern,
    MatchingEngine,
    RecommendationType,
)


@pytest.fixture()
def langchain_profile() -> AgentProfile:
    return AgentProfile(
        framework="langchain",
        framework_confidence=0.94,
        model_id="gpt-4o",
        detected_patterns=[DetectedPattern.STRUCTURED_EXTRACTION],
        task_completion_rate=0.72,
        cost_per_task_usd=0.045,
        loc=180,
        cyclomatic_complexity=24,
        waste_score=58.0,
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
        ),
        freshness_score=1.0,
    )


@pytest.fixture()
def langchain_candidate() -> AlternativeCandidate:
    """Same framework as the agent — should be filtered out."""
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
        assert dominance is not None
        # 180 → 90 LOC = 50 % reduction, must clear ≥ 40 % threshold
        assert "complexity" in dominance.winning_axes
        assert dominance.complexity_delta_pct is not None
        assert dominance.complexity_delta_pct >= 40.0

    def test_same_framework_not_recommended(
        self,
        langchain_profile: AgentProfile,
        langchain_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[langchain_candidate])
        ranked = engine.rank(langchain_profile)

        assert ranked == [], "Must not recommend the agent's existing framework"

    def test_pydanticai_ranked_above_langchain_when_both_present(
        self,
        langchain_profile: AgentProfile,
        pydanticai_candidate: AlternativeCandidate,
        langchain_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[langchain_candidate, pydanticai_candidate])
        ranked = engine.rank(langchain_profile)

        # LangChain filtered out; only PydanticAI should appear
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

        dominance = ranked[0].dominance
        assert dominance is not None
        # $0.045 → $0.028 = 37.8 % cost reduction, clears ≥ 30 % threshold
        assert "cost" in dominance.winning_axes
