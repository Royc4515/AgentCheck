from __future__ import annotations

"""Cocky AI-generated verdict for check #4.

Calls an OpenAI-compatible chat-completions endpoint (Groq / OpenRouter /
local Ollama) to generate a short, personality-driven roast of the audited
agent based on the FullComparisonReport.

API key precedence: explicit ``api_key`` arg → ``$GROQ_API_KEY`` →
``$OPENROUTER_API_KEY``. If no key is set, or the request fails for any
reason, the function returns an empty string — the rest of the report
renders normally.
"""

import os
import textwrap
from typing import Optional

import requests

from .models import FullComparisonReport

_DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"
_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_DEFAULT_TIMEOUT = 20.0

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are AgentCheck — a brilliantly cocky AI auditing tool with the energy
    of a smug senior engineer who has seen every AI anti-pattern imaginable.
    You have zero patience for bloat, mediocrity, or over-engineered nonsense.
    You speak in short, punchy sentences. You're funny because you're right.
    You roast the agent being audited, not the developer personally.
    You always end with one concrete next step.
    No bullet points. No markdown. No hashtags. Pure scorching prose.
""")


def _build_prompt(report: FullComparisonReport) -> str:
    s = report.overall_score
    profile = report.agent_profile

    grade = s.overall_grade.value if s and s.overall_grade else "?"
    overall = f"{s.overall_score:.0f}/100" if s and s.overall_score is not None else "unknown"

    reliability_line = (
        f"{s.reliability_score:.0f}/100 ({profile.task_completion_rate:.0%} task completion)"
        if s and s.reliability_score is not None and profile.task_completion_rate is not None
        else "unknown"
    )
    efficiency_line = (
        f"{s.efficiency_score:.0f}/100 (${profile.cost_per_task_usd:.4f}/task)"
        if s and s.efficiency_score is not None and profile.cost_per_task_usd is not None
        else "unknown"
    )
    security_line = (
        f"{s.security_score:.0f}/100 ({profile.security_finding_count} findings)"
        if s and s.security_score is not None and profile.security_finding_count is not None
        else "unknown"
    )

    framework = profile.framework or "unknown framework"
    model = profile.model_id or "unknown model"

    top_alts = [c.candidate.name for c in report.comparisons[:3]]
    alts_line = ", ".join(top_alts) if top_alts else "nothing in the KB could save you"

    wastefulness = profile.wastefulness
    bloat_line = ""
    if wastefulness and wastefulness.token_bloat_pct:
        bloat_line = f"token bloat: {wastefulness.token_bloat_pct:.0f}% above baseline. "
    if wastefulness and wastefulness.model_over_spec and wastefulness.suggested_model:
        bloat_line += f"A {wastefulness.suggested_model} would've been fine."

    return textwrap.dedent(f"""\
        I just audited an AI agent. Here's the damage:

        Framework: {framework}
        Model: {model}
        Overall grade: {grade} ({overall})
        Reliability: {reliability_line}
        Efficiency: {efficiency_line}
        {f"Waste detail: {bloat_line}" if bloat_line else ""}Security: {security_line}
        Suggested alternatives: {alts_line}

        Write a 3-sentence verdict in your cocky persona.
        Sentence 1: roast the specific grade and what it means.
        Sentence 2: pick the most embarrassing metric and twist the knife.
        Sentence 3: give one actionable next step, still with attitude.
    """).strip()


class VerdictGenerator:
    """Generates the cocky AI verdict via an OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = _DEFAULT_MODEL,
        url: str = _DEFAULT_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("GROQ_API_KEY", "") or os.environ.get(
                "OPENROUTER_API_KEY", ""
            )
        self._api_key = api_key
        self._model = model
        self._url = url
        self._timeout = timeout

    def generate(self, report: FullComparisonReport) -> str:
        """Return the roast text, or '' if unavailable."""
        if not self._api_key:
            return ""

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(report)},
            ],
            "temperature": 0.9,
            "max_tokens": 250,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self._url, headers=headers, json=payload, timeout=self._timeout
            )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception:  # noqa: BLE001 — never crash the report over a roast
            return ""
