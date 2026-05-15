"""Single LLM client routed through Groq (OpenAI-compatible).

All LLM calls across AgentCheck flow through this module so we can change
provider, key, or model in exactly one place. The key is read from the
``GROQ_API_KEY`` env var (with ``OPENROUTER_API_KEY`` as a fallback for
legacy setups) — never hardcoded.

Fallback: if Groq is unavailable or rate-limited, the client automatically
retries against a local Podman/Ollama inference server when ``LOCAL_LLM_URL``
is set in the environment.
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
_RETRY_DELAYS = (5.0, 15.0, 30.0)  # seconds between retries on 429

# Local Podman/Ollama fallback — set these env vars to enable
# LOCAL_LLM_URL   e.g. http://localhost:11434/v1/chat/completions  (Ollama)
#                      http://localhost:8080/v1/chat/completions    (AI Lab)
# LOCAL_LLM_MODEL e.g. llama3.2  (must match a model loaded in Podman)
_LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "")
_LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "llama3.2")


class OpenRouterError(RuntimeError):
    """Raised when the LLM call cannot be completed."""


class OpenRouterClient:
    """Minimal chat-completions client for Groq with local Podman fallback."""

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
        self._local_url = os.environ.get("LOCAL_LLM_URL", _LOCAL_LLM_URL)
        self._local_model = os.environ.get("LOCAL_LLM_MODEL", _LOCAL_LLM_MODEL)

    @property
    def has_key(self) -> bool:
        return bool(self._api_key) or bool(self._local_url)

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

        Try order:
          1. Groq (with retry on 429 using Retry-After header)
          2. Local Podman/Ollama fallback (if LOCAL_LLM_URL is set)

        Raises OpenRouterError if both providers fail.
        """
        if not self._api_key and not self._local_url:
            raise OpenRouterError(
                "No LLM provider configured. Set GROQ_API_KEY or LOCAL_LLM_URL."
            )

        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        groq_error: Optional[Exception] = None

        # --- 1. Try Groq ---
        if self._api_key:
            try:
                return self._call_groq(payload)
            except OpenRouterError as exc:
                groq_error = exc
                if self._local_url:
                    print(f"   [Groq] Failed ({exc}). Falling back to local LLM...")
                else:
                    raise

        # --- 2. Try local Podman/Ollama fallback ---
        if self._local_url:
            local_payload = {**payload, "model": self._local_model}
            # local models often don't support json response_format
            local_payload.pop("response_format", None)
            try:
                return self._call_local(local_payload)
            except OpenRouterError as local_exc:
                if groq_error:
                    raise OpenRouterError(
                        f"Both Groq and local LLM failed. "
                        f"Groq: {groq_error}. Local: {local_exc}"
                    ) from local_exc
                raise

        raise OpenRouterError(str(groq_error))

    def _call_groq(self, payload: dict[str, Any]) -> str:
        """Call Groq with retry-on-429 logic."""
        last_exc: Exception = RuntimeError("unreachable")
        for delay in (*_RETRY_DELAYS, None):
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
                if response.status_code == 429:
                    if delay is not None:
                        wait = float(response.headers.get("retry-after", delay))
                        print(f"   [Groq] Rate limited, retrying in {wait:.0f}s...")
                        time.sleep(wait)
                        continue
                    # exhausted retries
                    raise OpenRouterError("Groq rate limit — retries exhausted (429)")
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
                    wait = float(exc.response.headers.get("retry-after", delay))
                    print(f"   [Groq] Rate limited, retrying in {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                raise OpenRouterError(f"Groq call failed: {exc}") from exc
        raise OpenRouterError(f"Groq call failed after retries: {last_exc}") from last_exc

    def _call_local(self, payload: dict[str, Any]) -> str:
        """Call the local Podman/Ollama inference server (no auth)."""
        try:
            response = requests.post(
                self._local_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise OpenRouterError(f"Local LLM call failed: {exc}") from exc

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
