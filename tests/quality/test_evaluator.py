"""Unit tests for QualityEvaluator scoring logic."""

import json
from unittest.mock import MagicMock, call

import pytest

from agentcheck.quality.evaluator import QualityEvaluator


def _client(*responses: str) -> MagicMock:
    client = MagicMock()
    client.generate.side_effect = list(responses)
    return client


def _score(n: int) -> str:
    return json.dumps({"score": n, "reason": "ok"})


_METRICS = [
    {"metric_name": "Task Accuracy", "rubric": "Score 100 if the task was done."},
    {"metric_name": "Conciseness", "rubric": "Score 100 if brief."},
]


class TestEvaluateMetric:
    def test_returns_score_and_reason(self):
        ev = QualityEvaluator(_client(_score(85)))
        result = ev.evaluate_metric("Great answer", "Task Accuracy", "Score 100 if correct.")

        assert result["score"] == 85
        assert result["reason"] == "ok"

    def test_includes_metric_name_in_llm_prompt(self):
        client = _client(_score(70))
        ev = QualityEvaluator(client)
        ev.evaluate_metric("output", "Task Accuracy", "some rubric")

        llm_prompt = client.generate.call_args[0][0]
        assert "Task Accuracy" in llm_prompt

    def test_includes_rubric_in_llm_prompt(self):
        client = _client(_score(70))
        ev = QualityEvaluator(client)
        ev.evaluate_metric("output", "Conciseness", "Score 100 if brief and focused.")

        llm_prompt = client.generate.call_args[0][0]
        assert "Score 100 if brief and focused." in llm_prompt

    def test_includes_agent_output_in_llm_prompt(self):
        client = _client(_score(70))
        ev = QualityEvaluator(client)
        ev.evaluate_metric("The capital of France is Paris.", "accuracy", "rubric")

        llm_prompt = client.generate.call_args[0][0]
        assert "The capital of France is Paris." in llm_prompt

    def test_includes_test_prompt_when_provided(self):
        client = _client(_score(90))
        ev = QualityEvaluator(client)
        ev.evaluate_metric(
            "Paris is the capital.",
            "Task Accuracy",
            "rubric",
            test_prompt="What is the capital of France?",
        )

        llm_prompt = client.generate.call_args[0][0]
        assert "What is the capital of France?" in llm_prompt

    def test_omits_prompt_section_when_not_provided(self):
        client = _client(_score(80))
        ev = QualityEvaluator(client)
        ev.evaluate_metric("output", "metric", "rubric")

        llm_prompt = client.generate.call_args[0][0]
        assert "Original Test Prompt" not in llm_prompt

    def test_invalid_json_returns_score_zero(self):
        ev = QualityEvaluator(_client("not json"))
        result = ev.evaluate_metric("output", "metric", "rubric")

        assert result["score"] == 0
        assert "reason" in result

    def test_empty_response_returns_score_zero(self):
        ev = QualityEvaluator(_client(""))
        result = ev.evaluate_metric("output", "metric", "rubric")

        assert result["score"] == 0


class TestEvaluateAllScoringLogic:
    def test_single_test_single_metric_score(self):
        ev = QualityEvaluator(_client(_score(80)))
        result = ev.evaluate_all({"test1": "output"}, [_METRICS[0]])

        assert result["breakdown"]["test1"]["score"] == 80.0
        assert result["final_score"] == 80.0

    def test_averages_metric_scores_per_test(self):
        # Two metrics: 80 and 60 → avg = 70
        ev = QualityEvaluator(_client(_score(80), _score(60)))
        result = ev.evaluate_all({"test1": "output"}, _METRICS)

        assert result["breakdown"]["test1"]["score"] == pytest.approx(70.0)

    def test_final_score_is_average_across_tests(self):
        # test1 = 100, test2 = 60 → final = 80
        ev = QualityEvaluator(_client(_score(100), _score(60)))
        result = ev.evaluate_all(
            {"test1": "output1", "test2": "output2"},
            [_METRICS[0]],
        )

        assert result["final_score"] == pytest.approx(80.0)

    def test_breakdown_contains_all_tests(self):
        ev = QualityEvaluator(_client(_score(70), _score(90)))
        result = ev.evaluate_all(
            {"alpha": "output1", "beta": "output2"},
            [_METRICS[0]],
        )

        assert "alpha" in result["breakdown"]
        assert "beta" in result["breakdown"]

    def test_breakdown_contains_metric_details(self):
        ev = QualityEvaluator(_client(_score(75), _score(55)))
        result = ev.evaluate_all({"t1": "out"}, _METRICS)

        details = result["breakdown"]["t1"]["details"]
        assert "Task Accuracy" in details
        assert "Conciseness" in details

    def test_empty_outputs_returns_zero_final_score(self):
        ev = QualityEvaluator(_client())
        result = ev.evaluate_all({}, _METRICS)

        assert result["final_score"] == 0
        assert result["breakdown"] == {}

    def test_empty_metrics_gives_each_test_score_zero(self):
        ev = QualityEvaluator(_client())
        result = ev.evaluate_all({"t1": "out"}, [])

        assert result["breakdown"]["t1"]["score"] == 0
        assert result["final_score"] == 0

    def test_passes_test_prompts_to_metric_evaluator(self):
        client = _client(_score(90))
        ev = QualityEvaluator(client)
        ev.evaluate_all(
            {"greet": "Hello there!"},
            [_METRICS[0]],
            test_prompts={"greet": "Say hello"},
        )

        llm_prompt = client.generate.call_args[0][0]
        assert "Say hello" in llm_prompt

    def test_scores_below_threshold_do_not_count_as_passed(self):
        # Only tests with score >= 60 count as passing in the runner
        ev = QualityEvaluator(_client(_score(40)))
        result = ev.evaluate_all({"t1": "bad output"}, [_METRICS[0]])

        assert result["breakdown"]["t1"]["score"] == pytest.approx(40.0)

    def test_score_of_exactly_60_is_at_threshold(self):
        ev = QualityEvaluator(_client(_score(60)))
        result = ev.evaluate_all({"t1": "borderline"}, [_METRICS[0]])

        assert result["breakdown"]["t1"]["score"] == pytest.approx(60.0)

    def test_multiple_tests_multiple_metrics_math(self):
        # test1: metric A=80, metric B=100 → avg=90
        # test2: metric A=40, metric B=60  → avg=50
        # final = (90 + 50) / 2 = 70
        ev = QualityEvaluator(
            _client(_score(80), _score(100), _score(40), _score(60))
        )
        result = ev.evaluate_all(
            {"test1": "out1", "test2": "out2"},
            _METRICS,
        )

        assert result["breakdown"]["test1"]["score"] == pytest.approx(90.0)
        assert result["breakdown"]["test2"]["score"] == pytest.approx(50.0)
        assert result["final_score"] == pytest.approx(70.0)
