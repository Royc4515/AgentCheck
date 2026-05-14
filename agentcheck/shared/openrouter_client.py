"""Single LLM client routed through Groq (OpenAI-compatible).

All LLM calls across AgentCheck flow through this module so we can change
provider, key, or model in exactly one place. The key is read from the
``GROQ_API_KEY`` env var (with ``OPENROUTER_API_KEY`` as a fallback for
legacy setups) — never hardcoded.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import requests

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_TIMEOUT = 30.0
_RETRY_DELAYS = (2.0, 4.0, 8.0)  # seconds between retries on 429


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

        Retries up to 3 times with exponential backoff on 429 rate-limit
        responses. Raises OpenRouterError on any unrecoverable failure.
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

        last_exc: Exception = RuntimeError("unreachable")
        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
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
                if response.status_code == 429 and delay is not None:
                    print(f"   [Groq] Rate limited, retrying in {delay:.0f}s...")
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except (requests.RequestException, KeyError, ValueError) as exc:
                last_exc = exc
                if (
                    isinstance(exc, requests.HTTPError)
                    and exc.response is not None
                    and exc.response.status_code == 429
                    and delay is not None
                ):
                    print(f"   [Groq] Rate limited, retrying in {delay:.0f}s...")
                    time.sleep(delay)
                    continue
                raise OpenRouterError(f"Groq call failed: {exc}") from exc

        raise OpenRouterError(f"Groq call failed after retries: {last_exc}") from last_exc

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
