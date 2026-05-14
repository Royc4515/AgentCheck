"""Sample target agent used to demo AgentCheck.

This agent calls Groq directly via the requests module — no openai
SDK required. The API key is read from the GROQ_API_KEY env var.
If the key is missing, the agent falls back to a deterministic stub so
AgentCheck can still be demoed offline.
"""

from __future__ import annotations

import os
from typing import Any

import requests

_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.3-70b-versatile"
_SYSTEM = (
    "You are a professional travel planner. "
    "Provide a short structured itinerary. "
    "Always include exactly 3 attractions and 1 local food tip."
)


def travel_planner_agent(prompt: str) -> str:
    """Plan a short trip for the given prompt."""
    api_key = os.environ.get("GROQ_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return (
            f"Itinerary for {prompt}:\n"
            "1. Local landmark\n2. Famous museum\n3. Scenic viewpoint\n"
            "Food tip: try the regional specialty."
        )

    payload: dict[str, Any] = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 400,
        "temperature": 0.7,
    }
    response = requests.post(
        _ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()
