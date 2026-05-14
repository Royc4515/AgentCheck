"""Unit tests for DynamicTestGenerator (generation logic)."""

import json
from unittest.mock import MagicMock

import pytest

from agentcheck.quality.generator import DynamicTestGenerator


def _make_client(response: str) -> MagicMock:
    client = MagicMock()
    client.generate.return_value = response
    return client


def _valid_suite(n_tests: int = 2) -> str:
    return json.dumps(
        {
            "tests": [
                {"name": f"Test {i}", "prompt": f"prompt {i}", "type": "happy_path"}
                for i in range(n_tests)
            ],
            "custom_metrics": [
                {"metric_name": "Task Accuracy", "rubric": "Score 100 if correct."},
                {"metric_name": "Conciseness", "rubric": "Score 100 if brief."},
            ],
        }
    )


class TestGenerateSuiteStructure:
    def test_returns_tests_and_metrics_keys(self):
        gen = DynamicTestGenerator(_make_client(_valid_suite()))
        suite = gen.generate_suite("travel planner")

        assert "tests" in suite
        assert "custom_metrics" in suite

    def test_tests_have_required_fields(self):
        gen = DynamicTestGenerator(_make_client(_valid_suite(3)))
        suite = gen.generate_suite("travel planner")

        for t in suite["tests"]:
            assert "name" in t
            assert "prompt" in t
            assert "type" in t

    def test_metrics_have_required_fields(self):
        gen = DynamicTestGenerator(_make_client(_valid_suite()))
        suite = gen.generate_suite("travel planner")

        for m in suite["custom_metrics"]:
            assert "metric_name" in m
            assert "rubric" in m

    def test_test_count_matches_llm_response(self):
        gen = DynamicTestGenerator(_make_client(_valid_suite(5)))
        suite = gen.generate_suite("some agent")

        assert len(suite["tests"]) == 5


class TestGenerateSuiteLLMInteraction:
    def test_calls_llm_exactly_once(self):
        client = _make_client(_valid_suite())
        gen = DynamicTestGenerator(client)
        gen.generate_suite("some agent")

        client.generate.assert_called_once()

    def test_agent_purpose_is_in_llm_prompt(self):
        client = _make_client(_valid_suite())
        gen = DynamicTestGenerator(client)
        gen.generate_suite("customer support chatbot")

        llm_prompt = client.generate.call_args[0][0]
        assert "customer support chatbot" in llm_prompt

    def test_different_purposes_produce_different_prompts(self):
        client = _make_client(_valid_suite())
        gen = DynamicTestGenerator(client)

        gen.generate_suite("agent A")
        prompt_a = client.generate.call_args[0][0]

        gen.generate_suite("agent B")
        prompt_b = client.generate.call_args[0][0]

        assert prompt_a != prompt_b


class TestGenerateSuiteErrorHandling:
    def test_invalid_json_returns_empty_structure(self):
        gen = DynamicTestGenerator(_make_client("not {{ valid json"))
        suite = gen.generate_suite("some agent")

        assert suite == {"tests": [], "custom_metrics": []}

    def test_empty_string_response_returns_empty_structure(self):
        gen = DynamicTestGenerator(_make_client(""))
        suite = gen.generate_suite("some agent")

        assert suite == {"tests": [], "custom_metrics": []}

    def test_partial_json_still_returns_empty_structure(self):
        gen = DynamicTestGenerator(_make_client('{"tests": ['))
        suite = gen.generate_suite("some agent")

        assert suite == {"tests": [], "custom_metrics": []}

    def test_json_missing_tests_key(self):
        client = _make_client(json.dumps({"custom_metrics": []}))
        gen = DynamicTestGenerator(client)
        suite = gen.generate_suite("some agent")

        assert "tests" in suite
        assert suite["tests"] == []

    def test_json_missing_metrics_key(self):
        client = _make_client(json.dumps({"tests": []}))
        gen = DynamicTestGenerator(client)
        suite = gen.generate_suite("some agent")

        assert "custom_metrics" in suite
        assert suite["custom_metrics"] == []
