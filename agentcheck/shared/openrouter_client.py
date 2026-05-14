"""Single LLM client routed through Groq (OpenAI-compatible).

All LLM calls across AgentCheck flow through this module so we can change
provider, key, or model in exactly one place. The key is read from the
``GROQ_API_KEY`` env var (with ``OPENROUTER_API_KEY`` as a fallback for
legacy setups) — never hardcoded.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_TIMEOUT = 30.0


class OpenRouterError(RuntimeError):
    """Raised when the LLM call cannot be completed."""


class OpenRouterClient:
    """Minimal chat-completions client for Groq (OpenAI-compatible API)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        timeout: float = _DEFAULT_TIMEOUT,
        referer: str = "https://github.com/royc4515/agentcheck",
        title: str = "AgentCheck",
    ) -> None:
        self._api_key = (
            api_key
            or os.environ.get("GROQ_API_KEY", "")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )
        self._model = model
        self._timeout = timeout
        self._referer = referer
        self._title = title

    @property
    def has_key(self) -> bool:
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        """Send a chat-completions request and return the assistant text.

        Raises OpenRouterError on any failure (no key, network, bad payload).
        Callers that prefer a soft-fail pattern should catch it.
        """
        if not self._api_key:
            raise OpenRouterError(
                "GROQ_API_KEY is not set. Export it before running AgentCheck."
            )

        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                _GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise OpenRouterError(f"Groq call failed: {exc}") from exc

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """Convenience wrapper that asks for json_object mode and parses the result."""
        text = self.chat(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise OpenRouterError(f"Model did not return valid JSON: {exc}") from exc
