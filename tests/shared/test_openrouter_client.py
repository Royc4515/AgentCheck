"""Tests for the LLM client — covers Groq + local Ollama/Podman fallback."""

from unittest.mock import MagicMock, patch

import pytest

from agentcheck.shared.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
)


def _ok_response(text: str = "hi") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": text}}]}
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


def _err_response(status: int = 500) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {}

    def _raise() -> None:
        import requests

        raise requests.HTTPError(f"{status} error")

    resp.raise_for_status.side_effect = _raise
    return resp


class TestNoProvider:
    def test_raises_when_neither_key_nor_local_url(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("LOCAL_LLM_URL", raising=False)
        client = OpenRouterClient()
        with pytest.raises(OpenRouterError):
            client.chat([{"role": "user", "content": "hi"}])


class TestGroqOnly:
    def test_calls_groq_when_key_set(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.delenv("LOCAL_LLM_URL", raising=False)
        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.return_value = _ok_response("groq says hi")
            client = OpenRouterClient()
            out = client.chat([{"role": "user", "content": "ping"}])
        assert out == "groq says hi"
        assert "groq.com" in mock_post.call_args.args[0]


class TestLocalOnly:
    """Local fallback works when LOCAL_LLM_URL is the ONLY provider configured."""

    def test_calls_local_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "llama3.2")
        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.return_value = _ok_response("local says hi")
            client = OpenRouterClient()
            out = client.chat([{"role": "user", "content": "ping"}])
        assert out == "local says hi"
        called_url = mock_post.call_args.args[0]
        assert "localhost:11434" in called_url

    def test_local_payload_uses_local_model(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "llama3.2")
        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.return_value = _ok_response("ok")
            OpenRouterClient().chat([{"role": "user", "content": "ping"}])
        body = mock_post.call_args.kwargs["json"]
        assert body["model"] == "llama3.2"

    def test_local_strips_response_format_json_mode(self, monkeypatch):
        """Most local Ollama models don't support response_format — it must be stripped."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.return_value = _ok_response('{"k":"v"}')
            OpenRouterClient().chat(
                [{"role": "user", "content": "ping"}], json_mode=True
            )
        body = mock_post.call_args.kwargs["json"]
        assert "response_format" not in body

    def test_local_sends_no_auth_header(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.return_value = _ok_response("ok")
            OpenRouterClient().chat([{"role": "user", "content": "ping"}])
        headers = mock_post.call_args.kwargs["headers"]
        assert "Authorization" not in headers

    def test_local_failure_raises_openrouter_error(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.side_effect = RuntimeError("connection refused")
            with pytest.raises(OpenRouterError):
                OpenRouterClient().chat([{"role": "user", "content": "ping"}])


class TestGroqFallsBackToLocal:
    def test_groq_429_falls_back_to_local(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "llama3.2")

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {}

        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.side_effect = [rate_limited, _ok_response("local fallback hi")]
            out = OpenRouterClient().chat([{"role": "user", "content": "ping"}])

        assert out == "local fallback hi"
        # Groq attempted first, then local
        assert mock_post.call_count == 2
        assert "groq.com" in mock_post.call_args_list[0].args[0]
        assert "localhost" in mock_post.call_args_list[1].args[0]

    def test_groq_network_error_falls_back_to_local(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")

        import requests as _r

        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.side_effect = [
                _r.ConnectionError("groq unreachable"),
                _ok_response("local rescue"),
            ]
            out = OpenRouterClient().chat([{"role": "user", "content": "ping"}])

        assert out == "local rescue"

    def test_both_failed_raises_with_both_errors(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("LOCAL_LLM_URL", "http://localhost:11434/v1/chat/completions")

        with patch("agentcheck.shared.openrouter_client.requests.post") as mock_post:
            mock_post.side_effect = [
                RuntimeError("groq down"),
                RuntimeError("local down"),
            ]
            with pytest.raises(OpenRouterError) as exc_info:
                OpenRouterClient().chat([{"role": "user", "content": "ping"}])

        msg = str(exc_info.value)
        assert "Groq" in msg
        assert "local" in msg.lower()
