"""LLM-driven classification: is each finding necessary or unnecessary?"""

from __future__ import annotations

import time  # 🟢 הוספנו בשביל למנוע חסימות RPM
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
            f.rationale = "GROQ_API_KEY not set; skipped LLM classification."
        return findings

    # 🟢 DEMO MODE HACK: נסווג רק את ה-3 הראשונים כדי לחסוך טוקנים, זמן וחסימות
    max_to_classify = 3 

    for i, f in enumerate(findings):
        # אם עברנו את המכסה של הדמו, מדלגים על ה-LLM
        if i >= max_to_classify:
            f.classification = "unclassified"
            f.rationale = "Skipped LLM classification to save API tokens during demo."
            continue

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
                max_tokens=150, # 🟢 הורדנו מ-300 ל-150. פחות חפירות = פחות טוקנים
            )
            f.classification = str(result.get("classification", "unclassified")).lower()
            f.rationale = str(result.get("rationale", ""))[:500]
            
            # 🟢 מגנים על ה-API מקריסה (Rate Limit Prevention)
            time.sleep(1.2) 
            
        except OpenRouterError as exc:
            f.classification = "unclassified"
            f.rationale = f"LLM classification failed: {exc}"
            
    return findings