from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# The three per-check contract models live in shared/ so Parts 1/2/3 can
# validate their output without pulling in the alternatives engine.
from agentcheck.shared.models import (
    ReliabilityResult,
    SecurityResult,
    WastefulnessResult,
)


class RecommendationType(str, Enum):
    FRAMEWORK_SHIFT = "framework_shift"
    PATTERN_SHIFT = "pattern_shift"
    ARCHITECTURAL_SHIFT = "architectural_shift"
    MODEL_DOWNGRADE = "model_downgrade"
    DELETE_THE_LLM = "delete_the_llm"


class DetectedPattern(str, Enum):
    REACT_LOOP = "react_loop"
    PLAN_AND_EXECUTE = "plan_and_execute"
    RAG_PIPELINE = "rag_pipeline"
    SIMPLE_EXTRACTION = "simple_extraction"
    STRUCTURED_EXTRACTION = "structured_extraction"
    SINGLE_TOOL_CALL = "single_tool_call"
    DETERMINISTIC_TRANSFORM = "deterministic_transform"
    MULTI_AGENT_DEBATE = "multi_agent_debate"
    CODE_GENERATION_WITH_REVIEW = "code_generation_with_review"
    COMPLEX_RAG_PIPELINE = "complex_rag_pipeline"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Per-check result schemas live in agentcheck.shared.models — they are
# re-exported via the import at the top of this file.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Combined agent profile (what check #4 works with)
# ---------------------------------------------------------------------------

class AgentProfile(BaseModel):
    """Unified snapshot of the audited agent, populated from all three check JSONs.

    Any field that cannot be determined is left as None; the MatchingEngine
    degrades gracefully on sparse profiles.
    """

    # Static analysis / shared
    framework: Optional[str] = None
    framework_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    model_id: Optional[str] = None
    detected_patterns: list[DetectedPattern] = Field(default_factory=list)

    # From check #1 (reliability_result.json)
    reliability: Optional[ReliabilityResult] = None

    # From check #2 (wastefulness_result.json)
    wastefulness: Optional[WastefulnessResult] = None

    # From check #3 (security_result.json)
    security: Optional[SecurityResult] = None

    # Convenience accessors so MatchingEngine code stays readable
    @property
    def task_completion_rate(self) -> Optional[float]:
        return self.reliability.task_completion_rate if self.reliability else None

    @property
    def cost_per_task_usd(self) -> Optional[float]:
        return self.wastefulness.cost_per_task_usd if self.wastefulness else None

    @property
    def loc(self) -> Optional[int]:
        return self.reliability.loc if self.reliability else None

    @property
    def cyclomatic_complexity(self) -> Optional[int]:
        return self.reliability.cyclomatic_complexity if self.reliability else None

    @property
    def waste_score(self) -> Optional[float]:
        return self.wastefulness.waste_score if self.wastefulness else None

    @property
    def security_finding_count(self) -> Optional[int]:
        return self.security.total_findings if self.security else None

    @field_validator("framework_confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        return round(v, 4)


# ---------------------------------------------------------------------------
# KB candidate models
# ---------------------------------------------------------------------------

class AlternativeMetrics(BaseModel):
    """Projected metrics for a KB candidate."""

    reliability_score: float = Field(ge=0.0, le=1.0)
    cost_per_task_usd: float = Field(ge=0.0)
    loc_estimate: int = Field(ge=0)
    cyclomatic_complexity: int = Field(ge=0)
    # Security: 0 = avoids the vulnerability class by design
    security_finding_count: int = Field(default=0, ge=0)


class DominanceResult(BaseModel):
    """Fitness assessment for a single KB candidate vs the current agent.

    'recommended' is True when the candidate improves at least one axis
    without regressing any other by more than 15 %.  Even when recommended
    is False the result is still surfaced — the report frames all candidates
    as "alternatives worth knowing about" with explicit trade-offs.
    """

    candidate_id: str
    recommended: bool  # True = clears the dominance bar

    # Per-axis delta as a signed percentage (positive = improvement)
    reliability_delta_pct: Optional[float] = None
    cost_delta_pct: Optional[float] = None
    complexity_delta_pct: Optional[float] = None
    security_delta_pct: Optional[float] = None

    better_on: list[str] = Field(default_factory=list)   # axes where alt is better
    worse_on: list[str] = Field(default_factory=list)    # axes where alt is worse

    trade_off_summary: str = ""

    # Keep 'dominates' as a read-only alias so existing tests don't break
    @property
    def dominates(self) -> bool:
        return self.recommended

    @property
    def winning_axes(self) -> list[str]:
        return self.better_on

    @property
    def regressed_axes(self) -> list[str]:
        return self.worse_on


class AlternativeCandidate(BaseModel):
    """A single KB entry, enriched with dominance analysis."""

    id: str
    name: str
    recommendation_type: RecommendationType
    description: str = ""

    kb_metrics: AlternativeMetrics
    dominance: Optional[DominanceResult] = None

    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)

    # Human-readable pros/cons from the KB YAML
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    code_example: Optional[str] = None
    evidence_url: Optional[str] = None

    # Per-field source tag.  Values are short strings like
    # "github_2026-05-14", "openrouter_2026-05-14", or "estimate".
    # Reporter uses these to badge measured metrics vs. hand-written estimates.
    data_provenance: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Overall score (synthesised from all three checks)
# ---------------------------------------------------------------------------

class LetterGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class OverallScore(BaseModel):
    """Composite health score derived from checks #1, #2, #3.

    Each axis is normalised to 0–100 (higher = better) then weighted:
        Reliability  40 %
        Efficiency   30 %  (inverted waste_score)
        Security     30 %
    """

    # Per-axis numeric scores (0–100, higher is better)
    reliability_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    efficiency_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    security_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    # Per-axis letter grades
    reliability_grade: Optional[LetterGrade] = None
    efficiency_grade: Optional[LetterGrade] = None
    security_grade: Optional[LetterGrade] = None

    # Weighted composite
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    overall_grade: Optional[LetterGrade] = None

    # Which checks contributed (depends on which JSONs were present)
    axes_available: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Comparison report (the actual output of check #4)
# ---------------------------------------------------------------------------

class CandidateComparison(BaseModel):
    """Side-by-side view of the original agent vs one alternative candidate."""

    candidate: AlternativeCandidate

    # Original values (from check JSONs)
    original_reliability: Optional[float] = None
    original_cost: Optional[float] = None
    original_loc: Optional[int] = None
    original_security_findings: Optional[int] = None

    # KB-projected values for the alternative
    alt_reliability: Optional[float] = None
    alt_cost: Optional[float] = None
    alt_loc: Optional[int] = None
    alt_security_findings: Optional[int] = None


class FullComparisonReport(BaseModel):
    """Top-level output of check #4."""

    agent_profile: AgentProfile
    overall_score: Optional[OverallScore] = None
    # Always the top 3 (or fewer if KB has fewer qualifying candidates)
    comparisons: list[CandidateComparison] = Field(default_factory=list)
    # Populated only in empirical mode (--validate-alternative)
    validation_results: list[ValidationResult] = Field(default_factory=list)

    kb_snapshot_date: str = ""
    total_candidates_evaluated: int = 0

    @property
    def top_recommendation(self) -> Optional[AlternativeCandidate]:
        for c in self.comparisons:
            if c.candidate.dominance and c.candidate.dominance.dominates:
                return c.candidate
        return None

    @property
    def has_actionable_recommendation(self) -> bool:
        return self.top_recommendation is not None


# ---------------------------------------------------------------------------
# Optional empirical validation (--validate-alternative)
# ---------------------------------------------------------------------------

class ValidationStatus(str, Enum):
    NOT_RUN = "not_run"
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class ValidationResult(BaseModel):
    """Result of the --validate-alternative empirical run (optional mode)."""

    candidate_id: str
    status: ValidationStatus = ValidationStatus.NOT_RUN

    generated_agent_path: Optional[str] = None
    task_completion_rate: Optional[float] = None
    cost_per_task_usd: Optional[float] = None

    confirmed_dominates: Optional[bool] = None
    error_message: Optional[str] = None


# Legacy alias so existing tests don't break
AlternativesReport = FullComparisonReport

# Re-export LetterGrade for convenience
__all__ = ["LetterGrade", "OverallScore"]
