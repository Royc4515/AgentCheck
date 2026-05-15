"""Smoke tests and mocked-API integration tests for run_quality."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentcheck.shared.models import ReliabilityResult
from agentcheck.quality import run_quality


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_json(score: int) -> str:
    return json.dumps({"score": score, "reason": "ok"})


_MOCK_SUITE = json.dumps(
    {
        "tests": [
            {
                "name": "Happy Path",
                "prompt": "Plan a weekend trip to Rome.",
                "type": "happy_path",
            },
            {
                "name": "Edge Case",
                "prompt": "What if I have zero budget?",
                "type": "edge_case",
            },
        ],
        "custom_metrics": [
            {
                "metric_name": "Task Accuracy",
                "rubric": "Score 100 if the task was completed correctly.",
            },
            {
                "metric_name": "Conciseness",
                "rubric": "Score 100 if the answer is brief and to the point.",
            },
        ],
    }
)


# ---------------------------------------------------------------------------
# No-API-key smoke tests (existing behaviour)
# ---------------------------------------------------------------------------

def test_run_quality_writes_reliability_json(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_quality(fixture_agent_path, fixture_results_dir)

    assert isinstance(result, ReliabilityResult)
    out = fixture_results_dir / "reliability_result.json"
    assert out.exists()
    parsed = ReliabilityResult.model_validate_json(out.read_text())
    assert parsed.tasks_total >= 1
    assert parsed.loc is not None and parsed.loc > 0


def test_run_quality_accepts_path_object(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_quality(Path(fixture_agent_path), fixture_results_dir)
    assert result.tasks_total >= 1


# ---------------------------------------------------------------------------
# Mocked-API integration tests (full flow)
# ---------------------------------------------------------------------------

def _make_chat_side_effect(*responses: str):
    """Build a side_effect list for OpenRouterClient.chat calls."""
    return list(responses)


def test_full_flow_generate_then_evaluate(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    """
    Full flow with mocked LLM:
      1. generate_suite is called once → returns 2 tests + 2 metrics
      2. agent is called for each test
      3. evaluate_all is called → scores are parsed and stored
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    # Sequence of chat() return values:
    # call 0: generate_suite → suite JSON
    # calls 1-4: evaluate_metric (2 tests × 2 metrics) → score JSON
    chat_responses = [
        _MOCK_SUITE,
        _score_json(90),  # Happy Path / Task Accuracy
        _score_json(80),  # Happy Path / Conciseness
        _score_json(70),  # Edge Case / Task Accuracy
        _score_json(60),  # Edge Case / Conciseness
    ]

    with patch(
        "agentcheck.quality.runner.OpenRouterClient"
    ) as MockClient:
        instance = MockClient.return_value
        instance.has_key = True
        instance.chat.side_effect = chat_responses

        result = run_quality(fixture_agent_path, fixture_results_dir)

    # 2 tests ran
    assert result.tasks_total == 2
    # Happy Path avg=(90+80)/2=85 ≥ 60 → pass; Edge Case avg=(70+60)/2=65 ≥ 60 → pass
    assert result.tasks_passed == 2
    assert result.task_completion_rate == 1.0


def test_full_flow_failing_tests_counted_correctly(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    """Tests that score below 60 are NOT counted as passed."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    chat_responses = [
        _MOCK_SUITE,
        _score_json(90),  # Happy Path / Task Accuracy
        _score_json(80),  # Happy Path / Conciseness
        _score_json(20),  # Edge Case / Task Accuracy — fail
        _score_json(30),  # Edge Case / Conciseness  — fail
    ]

    with patch("agentcheck.quality.runner.OpenRouterClient") as MockClient:
        instance = MockClient.return_value
        instance.has_key = True
        instance.chat.side_effect = chat_responses

        result = run_quality(fixture_agent_path, fixture_results_dir)

    assert result.tasks_total == 2
    assert result.tasks_passed == 1  # only Happy Path passes
    assert result.task_completion_rate == pytest.approx(0.5)


def test_full_flow_result_is_persisted(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    """reliability_result.json is written and parseable after a mocked run."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    chat_responses = [_MOCK_SUITE, _score_json(80), _score_json(80), _score_json(80), _score_json(80)]

    with patch("agentcheck.quality.runner.OpenRouterClient") as MockClient:
        instance = MockClient.return_value
        instance.has_key = True
        instance.chat.side_effect = chat_responses

        run_quality(fixture_agent_path, fixture_results_dir)

    out = fixture_results_dir / "reliability_result.json"
    assert out.exists()
    parsed = ReliabilityResult.model_validate_json(out.read_text())
    assert parsed.tasks_total == 2
    assert 0.0 <= parsed.task_completion_rate <= 1.0


def test_full_flow_empty_suite_uses_smoke_test(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    """When the LLM returns no tests, the runner falls back to a single smoke prompt."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    empty_suite = json.dumps({"tests": [], "custom_metrics": []})

    with patch("agentcheck.quality.runner.OpenRouterClient") as MockClient:
        instance = MockClient.return_value
        instance.has_key = True
        instance.chat.return_value = empty_suite

        result = run_quality(fixture_agent_path, fixture_results_dir)

    # Fallback smoke test should still run
    assert result.tasks_total >= 1


def test_full_flow_uses_provided_task_as_purpose(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    """When a task is supplied the generator receives it as the agent purpose."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    captured_prompts: list[str] = []

    def capturing_chat(messages, **kwargs):
        for msg in messages:
            if msg["role"] == "user":
                captured_prompts.append(msg["content"])
        return _MOCK_SUITE

    with patch("agentcheck.quality.runner.OpenRouterClient") as MockClient:
        instance = MockClient.return_value
        instance.has_key = True
        instance.chat.side_effect = capturing_chat

        run_quality(
            fixture_agent_path,
            fixture_results_dir,
            task="book flight tickets",
        )

    assert any("book flight tickets" in p for p in captured_prompts)


# ---------------------------------------------------------------------------
# 2-param agent (prompt + api_key) — regression test for _invoke_agent fix
# ---------------------------------------------------------------------------

def test_two_param_agent_receives_api_key(
    fixture_results_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    """Agents with signature (prompt, api_key) must be invoked correctly."""
    agent_src = '''
def my_agent(prompt, api_key):
    return f"called with key={api_key}: {prompt}"
'''
    agent_path = tmp_path / "two_param_agent.py"
    agent_path.write_text(agent_src)

    monkeypatch.setenv("GROQ_API_KEY", "test-key-123")

    with patch("agentcheck.quality.runner.OpenRouterClient") as MockClient:
        instance = MockClient.return_value
        instance.has_key = False  # skip LLM generation — heuristic path

        result = run_quality(agent_path, fixture_results_dir)

    assert result.tasks_total >= 1
    # If _invoke_agent wrongly called fn(prompt) the output would be "[ERROR]"
    # and tasks_passed would be 0. A non-zero pass count proves the agent ran.
    assert result.tasks_passed >= 1
