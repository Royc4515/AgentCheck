"""LLM-driven classification: is each finding necessary or unnecessary?"""

from __future__ import annotations

from typing import Any

from agentcheck.shared import OpenRouterClient
from agentcheck.shared.openrouter_client import OpenRouterError

from .auditor import Finding


_SYSTEM = (
    "You are a senior application-security reviewer. "
    "Given an agent's purpose and a code-level finding, decide whether the "
    "risk is 'necessary' (unavoidable given the agent's job) or "
    "'unnecessary' (a real vulnerability that can and should be removed). "
    "Respond with strict JSON: {\"classification\": \"necessary\"|\"unnecessary\", \"rationale\": \"...\"}."
)


def classify_findings(
    findings: list[Finding],
    agent_purpose: str,
    client: OpenRouterClient | None = None,
) -> list[Finding]:
    """Annotate each finding with classification + rationale, in-place."""
    if not findings:
        return findings
    client = client or OpenRouterClient()
    if not client.has_key:
        for f in findings:
            f.classification = "unclassified"
            f.rationale = "OPENROUTER_API_KEY not set; skipped LLM classification."
        return findings

    for f in findings:
        prompt = (
            f"Agent purpose: {agent_purpose}\n"
            f"Finding: {f.title} (severity={f.severity})\n"
            f"Snippet (line {f.line}): {f.snippet}\n"
            f"Description: {f.description}"
        )
        try:
            result: dict[str, Any] = client.chat_json(
                [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=300,
            )
            f.classification = str(result.get("classification", "unclassified")).lower()
            f.rationale = str(result.get("rationale", ""))[:500]
        except OpenRouterError as exc:
            f.classification = "unclassified"
            f.rationale = f"LLM classification failed: {exc}"
    return findings
