"""Test #1 — The Honesty Test: Delete the LLM.

Scenario: an agent that extracts email addresses using an LLM call at
$0.003/call.  The KB contains the `delete_the_llm` architectural entry.
The MatchingEngine must surface it as the top recommendation because:
  - cost improves by 100 % (from $0.003 to $0.000)
  - reliability improves (deterministic > LLM for structured extraction)
  - no axis regresses past 15 %
"""

import pytest

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    AlternativesReport,
    DetectedPattern,
    DominanceResult,
    MatchingEngine,
    RecommendationType,
)


@pytest.fixture()
def delete_the_llm_candidate() -> AlternativeCandidate:
    return AlternativeCandidate(
        id="delete_the_llm",
        name="Delete the LLM",
        recommendation_type=RecommendationType.DELETE_THE_LLM,
        description="Replace LLM with a regex.",
        kb_metrics=AlternativeMetrics(
            reliability_score=0.99,
            cost_per_task_usd=0.000,
            loc_estimate=10,
            cyclomatic_complexity=2,
        ),
        freshness_score=1.0,
        code_example='import re\nemails = re.findall(r"[\\w.+-]+@[\\w-]+\\.[\\w.]+", text)',
    )


@pytest.fixture()
def email_extractor_profile() -> AgentProfile:
    """Agent that calls an LLM to extract emails — a clear overkill scenario."""
    return AgentProfile(
        framework="raw_sdk",
        framework_confidence=0.95,
        model_id="claude-sonnet-4-6",
        detected_patterns=[DetectedPattern.SIMPLE_EXTRACTION],
        task_completion_rate=0.72,   # LLMs are imperfect on structured extraction
        cost_per_task_usd=0.003,
        loc=45,
        cyclomatic_complexity=6,
    )


class TestHonestyTest:
    def test_delete_the_llm_dominates(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        assert len(ranked) == 1, "Expected exactly one candidate"
        top = ranked[0]
        assert top.dominance is not None
        assert top.dominance.dominates is True

    def test_cost_axis_wins(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        dominance = ranked[0].dominance
        assert dominance is not None
        assert "cost" in dominance.winning_axes

    def test_reliability_axis_wins(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        dominance = ranked[0].dominance
        assert dominance is not None
        assert "reliability" in dominance.winning_axes

    def test_no_regressions(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        dominance = ranked[0].dominance
        assert dominance is not None
        assert dominance.regressed_axes == []

    def test_delete_the_llm_not_suggested_for_react_agent(
        self,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        """An agent running ReAct loops for multi-step reasoning should NOT get
        the 'delete the LLM' recommendation — it's not a deterministic task."""
        react_profile = AgentProfile(
            framework="langchain",
            framework_confidence=0.91,
            detected_patterns=[DetectedPattern.REACT_LOOP],
            task_completion_rate=0.80,
            cost_per_task_usd=0.045,
            loc=180,
        )
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(react_profile)

        assert ranked == [], (
            "delete_the_llm must not be recommended for ReAct agents"
        )
