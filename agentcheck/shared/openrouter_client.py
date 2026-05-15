"""Single LLM client supporting Gemini, Groq, and local Ollama.

Provider priority (first key found wins):
  1. GEMINI_API_KEY  → Gemini via OpenAI-compatible endpoint
  2. GROQ_API_KEY    → Groq
  3. OPENROUTER_API_KEY → Groq-compatible (legacy)
  4. LOCAL_LLM_URL   → local Ollama / Podman fallback

All LLM calls across AgentCheck flow through this module so you change
provider in exactly one place — just set the right env var.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

import requests

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.3-70b-versatile"

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
_GEMINI_MODEL = "gemini-2.0-flash"

_DEFAULT_TIMEOUT = 30.0
_RETRY_DELAYS = (5.0, 15.0, 30.0)  # seconds between retries on 429

# Local Podman/Ollama fallback — set these env vars to enable
# LOCAL_LLM_URL   e.g. http://localhost:11434/v1/chat/completions  (Ollama)
#                      http://localhost:8080/v1/chat/completions    (AI Lab)
# LOCAL_LLM_MODEL e.g. llama3.2  (must match a model loaded in Podman)
_LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "")
_LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "llama3.2")


def _DEFAULT_MODEL() -> str:
    return _GEMINI_MODEL if os.environ.get("GEMINI_API_KEY") else _GROQ_MODEL


class OpenRouterError(RuntimeError):
    """Raised when the LLM call cannot be completed."""


class OpenRouterClient:
    """Chat-completions client supporting Gemini, Groq, and local Ollama."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
        referer: str = "https://github.com/royc4515/agentcheck",
        title: str = "AgentCheck",
    ) -> None:
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        groq_key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")

        if api_key:
            # Explicit key passed — caller decides provider via url/model
            self._api_key = api_key
            self._primary_url = _GROQ_URL
            self._model = model or _GROQ_MODEL
        elif gemini_key:
            self._api_key = gemini_key
            self._primary_url = _GEMINI_URL
            self._model = model or _GEMINI_MODEL
        else:
            self._api_key = groq_key
            self._primary_url = _GROQ_URL
            self._model = model or _GROQ_MODEL

        self._timeout = timeout
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
                "No LLM provider configured. "
                "Set GEMINI_API_KEY, GROQ_API_KEY, or LOCAL_LLM_URL."
            )

        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        primary_error: Optional[Exception] = None
        provider_name = "Gemini" if self._primary_url == _GEMINI_URL else "Groq"

        # --- 1. Try primary provider (Gemini or Groq) ---
        if self._api_key:
            try:
                return self._call_primary(payload)
            except OpenRouterError as exc:
                primary_error = exc
                if self._local_url:
                    print(f"   [{provider_name}] Failed ({exc}). Falling back to local LLM...")
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
                if primary_error:
                    raise OpenRouterError(
                        f"Both {provider_name} and local LLM failed. "
                        f"{provider_name}: {primary_error}. Local: {local_exc}"
                    ) from local_exc
                raise

        raise OpenRouterError(str(primary_error))

    def _call_primary(self, payload: dict[str, Any]) -> str:
        """Call the primary provider (Gemini or Groq).

        On 429, fails fast when a local fallback is available so the caller
        can switch immediately. Otherwise retries with back-off.
        """
        provider = "Gemini" if self._primary_url == _GEMINI_URL else "Groq"
        try:
            response = requests.post(
                self._primary_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout,
            )
            if response.status_code == 429:
                if self._local_url:
                    raise OpenRouterError(f"{provider} rate limited (429)")
                for delay in _RETRY_DELAYS:
                    wait = float(response.headers.get("retry-after", delay))
                    print(f"   [{provider}] Rate limited, retrying in {wait:.0f}s...")
                    time.sleep(wait)
                    response = requests.post(
                        self._primary_url,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                        timeout=self._timeout,
                    )
                    if response.status_code != 429:
                        break
                else:
                    raise OpenRouterError(f"{provider} rate limit — retries exhausted (429)")
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except OpenRouterError:
            raise
        except Exception as exc:
            raise OpenRouterError(f"{provider} call failed: {exc}") from exc

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
        except Exception as exc:
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
