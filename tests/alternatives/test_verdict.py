"""Tests for the cocky AI verdict generator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentcheck.alternatives import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    DetectedPattern,
    FullComparisonReport,
    LetterGrade,
    OverallScore,
    RecommendationType,
    ReliabilityResult,
    WastefulnessResult,
    SecurityResult,
    AlternativesReporter,
)
from agentcheck.alternatives.verdict import VerdictGenerator, _build_prompt


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def full_report() -> FullComparisonReport:
    profile = AgentProfile(
        framework="langchain",
        model_id="claude-sonnet-4-6",
        detected_patterns=[DetectedPattern.REACT_LOOP],
        reliability=ReliabilityResult(
            task_completion_rate=0.72, tasks_passed=7, tasks_total=10,
            framework="langchain", loc=180, cyclomatic_complexity=24,
        ),
        wastefulness=WastefulnessResult(
            waste_score=68.0, cost_per_task_usd=0.045, baseline_cost_usd=0.014,
            token_bloat_pct=220.0, model_over_spec=True,
            suggested_model="claude-haiku-4-5",
        ),
        security=SecurityResult(
            is_safe=False, critical_count=1, high_count=2,
            hardcoded_secrets=True, prompt_injection_vulnerable=True,
        ),
    )
    alt = AlternativeCandidate(
        id="raw_sdk", name="Raw SDK",
        recommendation_type=RecommendationType.FRAMEWORK_SHIFT,
        kb_metrics=AlternativeMetrics(
            reliability_score=0.85, cost_per_task_usd=0.021,
            loc_estimate=75, cyclomatic_complexity=9,
        ),
        freshness_score=1.0,
    )
    from agentcheck.alternatives.models import CandidateComparison
    return FullComparisonReport(
        agent_profile=profile,
        overall_score=OverallScore(
            reliability_score=72.0, efficiency_score=32.0, security_score=40.0,
            overall_score=50.4,
            reliability_grade=LetterGrade.C,
            efficiency_grade=LetterGrade.F,
            security_grade=LetterGrade.F,
            overall_grade=LetterGrade.F,
            axes_available=["reliability", "efficiency", "security"],
        ),
        comparisons=[CandidateComparison(
            candidate=alt,
            original_reliability=0.72, alt_reliability=0.85,
            original_cost=0.045, alt_cost=0.021,
        )],
        kb_snapshot_date="2026-05-14",
        total_candidates_evaluated=9,
    )


def _mock_openrouter_response(text: str):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": text}}]
    }
    return resp


# ---------------------------------------------------------------------------
# VerdictGenerator unit tests
# ---------------------------------------------------------------------------

class TestVerdictGenerator:
    def test_generates_roast_when_api_key_set(self, full_report: FullComparisonReport) -> None:
        expected = "Your agent is a trainwreck wrapped in LangChain abstractions."
        with patch("agentcheck.alternatives.verdict.requests.post") as mock_post:
            mock_post.return_value = _mock_openrouter_response(expected)
            gen = VerdictGenerator(api_key="sk-or-test-key")
            result = gen.generate(full_report)
        assert result == expected
        mock_post.assert_called_once()

    def test_returns_empty_string_when_no_api_key(self, full_report: FullComparisonReport) -> None:
        gen = VerdictGenerator(api_key="")
        result = gen.generate(full_report)
        assert result == ""

    def test_returns_empty_string_on_http_error(self, full_report: FullComparisonReport) -> None:
        with patch("agentcheck.alternatives.verdict.requests.post") as mock_post:
            mock_post.side_effect = RuntimeError("connection refused")
            gen = VerdictGenerator(api_key="sk-or-test-key")
            result = gen.generate(full_report)
        assert result == ""

    def test_returns_empty_string_on_bad_response(self, full_report: FullComparisonReport) -> None:
        with patch("agentcheck.alternatives.verdict.requests.post") as mock_post:
            resp = MagicMock()
            resp.json.return_value = {"unexpected": "format"}  # missing choices
            mock_post.return_value = resp
            gen = VerdictGenerator(api_key="sk-or-test-key")
            result = gen.generate(full_report)
        assert result == ""

    def test_reads_api_key_from_env(
        self, full_report: FullComparisonReport, monkeypatch
    ) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-from-env")
        with patch("agentcheck.alternatives.verdict.requests.post") as mock_post:
            mock_post.return_value = _mock_openrouter_response("Roast!")
            gen = VerdictGenerator()  # no explicit key
            gen.generate(full_report)
        call_headers = mock_post.call_args.kwargs["headers"]
        assert "sk-or-from-env" in call_headers["Authorization"]

    def test_request_uses_correct_model_and_temperature(
        self, full_report: FullComparisonReport
    ) -> None:
        with patch("agentcheck.alternatives.verdict.requests.post") as mock_post:
            mock_post.return_value = _mock_openrouter_response("test")
            VerdictGenerator(api_key="k", model="anthropic/claude-haiku-4-5-20251001").generate(full_report)
        body = mock_post.call_args.kwargs["json"]
        assert body["model"] == "anthropic/claude-haiku-4-5-20251001"
        assert body["temperature"] == 0.9
        assert body["max_tokens"] == 250


class TestBuildPrompt:
    def test_includes_framework_and_grade(self, full_report: FullComparisonReport) -> None:
        prompt = _build_prompt(full_report)
        assert "langchain" in prompt
        assert "F" in prompt

    def test_includes_cost(self, full_report: FullComparisonReport) -> None:
        prompt = _build_prompt(full_report)
        assert "0.045" in prompt

    def test_includes_top_alternative(self, full_report: FullComparisonReport) -> None:
        prompt = _build_prompt(full_report)
        assert "Raw SDK" in prompt

    def test_includes_waste_detail(self, full_report: FullComparisonReport) -> None:
        prompt = _build_prompt(full_report)
        assert "220" in prompt  # token_bloat_pct


# ---------------------------------------------------------------------------
# Reporter integration
# ---------------------------------------------------------------------------

class TestReporterWithVerdict:
    def test_verdict_panel_rendered_when_text_returned(
        self, full_report: FullComparisonReport
    ) -> None:
        mock_gen = MagicMock(spec=VerdictGenerator)
        mock_gen.generate.return_value = "Your code called — it wants to be deleted."
        reporter = AlternativesReporter(mode="terminal", verdict_generator=mock_gen)
        # Should not raise; verify generate was called
        reporter.render(full_report)
        mock_gen.generate.assert_called_once_with(full_report)

    def test_verdict_silently_skipped_when_empty(
        self, full_report: FullComparisonReport
    ) -> None:
        mock_gen = MagicMock(spec=VerdictGenerator)
        mock_gen.generate.return_value = ""
        reporter = AlternativesReporter(mode="terminal", verdict_generator=mock_gen)
        reporter.render(full_report)  # should not raise

    def test_verdict_not_called_in_json_mode(
        self, full_report: FullComparisonReport
    ) -> None:
        mock_gen = MagicMock(spec=VerdictGenerator)
        reporter = AlternativesReporter(mode="json", verdict_generator=mock_gen)
        reporter.render(full_report)
        mock_gen.generate.assert_not_called()

    def test_verdict_not_called_in_summary_mode(
        self, full_report: FullComparisonReport
    ) -> None:
        mock_gen = MagicMock(spec=VerdictGenerator)
        reporter = AlternativesReporter(mode="summary", verdict_generator=mock_gen)
        reporter.render(full_report)
        mock_gen.generate.assert_not_called()
