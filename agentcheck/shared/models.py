"""JSON contracts produced by each check.

Lives in ``shared`` (not ``alternatives``) so Parts 1/2/3 can validate their
own output without importing the alternatives engine and its transitive deps.
``agentcheck.alternatives.models`` re-exports these for backwards compatibility.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ReliabilityResult(BaseModel):
    """JSON contract for check #1 output (reliability_result.json)."""

    task_completion_rate: float = Field(ge=0.0, le=1.0)
    tasks_passed: int = Field(ge=0)
    tasks_total: int = Field(ge=1)
    framework: Optional[str] = None
    framework_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model_id: Optional[str] = None
    detected_patterns: list[str] = Field(default_factory=list)
    loc: Optional[int] = Field(default=None, ge=0)
    cyclomatic_complexity: Optional[int] = Field(default=None, ge=0)


class WastefulnessResult(BaseModel):
    """JSON contract for check #2 output (wastefulness_result.json)."""

    waste_score: float = Field(ge=0.0, le=100.0)
    cost_per_task_usd: float = Field(ge=0.0)
    baseline_cost_usd: float = Field(ge=0.0)
    token_bloat_pct: float = Field(default=0.0, ge=0.0)
    model_over_spec: bool = False
    suggested_model: Optional[str] = None
    redundant_tool_calls: int = Field(default=0, ge=0)
    retry_storms_detected: int = Field(default=0, ge=0)
    has_parallelizable_calls: bool = False


class SecurityResult(BaseModel):
    """JSON contract for check #3 output (security_result.json)."""

    is_safe: bool
    critical_count: int = Field(default=0, ge=0)
    high_count: int = Field(default=0, ge=0)
    medium_count: int = Field(default=0, ge=0)
    low_count: int = Field(default=0, ge=0)
    finding_ids: list[str] = Field(default_factory=list)
    hardcoded_secrets: bool = False
    prompt_injection_vulnerable: bool = False
    unsafe_deserialization: bool = False

    @property
    def total_findings(self) -> int:
        return self.critical_count + self.high_count + self.medium_count + self.low_count


__all__ = ["ReliabilityResult", "WastefulnessResult", "SecurityResult"]
