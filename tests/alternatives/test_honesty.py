"""Test #1 — The Honesty Test: Delete the LLM."""

import pytest

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    DetectedPattern,
    DominanceResult,
    MatchingEngine,
    ReliabilityResult,
    RecommendationType,
    WastefulnessResult,
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
            security_finding_count=0,
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
        reliability=ReliabilityResult(
            task_completion_rate=0.72,
            tasks_passed=7,
            tasks_total=10,
            framework="raw_sdk",
            framework_confidence=0.95,
            model_id="claude-sonnet-4-6",
            detected_patterns=["simple_extraction"],
            loc=45,
            cyclomatic_complexity=6,
        ),
        wastefulness=WastefulnessResult(
            waste_score=90.0,
            cost_per_task_usd=0.003,
            baseline_cost_usd=0.000,
        ),
    )


class TestHonestyTest:
    def test_delete_the_llm_dominates(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        assert len(ranked) == 1
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

        assert "cost" in ranked[0].dominance.winning_axes

    def test_reliability_axis_wins(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        assert "reliability" in ranked[0].dominance.winning_axes

    def test_no_regressions(
        self,
        email_extractor_profile: AgentProfile,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(email_extractor_profile)

        assert ranked[0].dominance.regressed_axes == []

    def test_delete_the_llm_not_suggested_for_react_agent(
        self,
        delete_the_llm_candidate: AlternativeCandidate,
    ) -> None:
        react_profile = AgentProfile(
            framework="langchain",
            framework_confidence=0.91,
            detected_patterns=[DetectedPattern.REACT_LOOP],
            reliability=ReliabilityResult(
                task_completion_rate=0.80,
                tasks_passed=8,
                tasks_total=10,
                loc=180,
            ),
            wastefulness=WastefulnessResult(
                waste_score=40.0,
                cost_per_task_usd=0.045,
                baseline_cost_usd=0.018,
            ),
        )
        engine = MatchingEngine(candidates=[delete_the_llm_candidate])
        ranked = engine.rank(react_profile)

        assert ranked == []
