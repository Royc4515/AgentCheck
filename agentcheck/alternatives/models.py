from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
# Per-check result schemas
# These define the JSON contracts that checks #1, #2, #3 must produce.
# ---------------------------------------------------------------------------

class ReliabilityResult(BaseModel):
    """JSON contract for check #1 output (reliability_result.json).

    Fields:
        task_completion_rate: fraction of tasks passed (0.0–1.0)
        tasks_passed: absolute count
        tasks_total: total tasks run
        framework: detected framework name
        framework_confidence: detection confidence (0.0–1.0)
        model_id: model used by the agent
        detected_patterns: list of DetectedPattern enum values
        loc: lines of code in agent source
        cyclomatic_complexity: average cyclomatic complexity
    """

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
    """JSON contract for check #2 output (wastefulness_result.json).

    Fields:
        waste_score: 0 (perfect) to 100 (catastrophic)
        cost_per_task_usd: actual measured cost per task
        baseline_cost_usd: theoretical minimum cost per task
        token_bloat_pct: excess tokens above baseline (%)
        model_over_spec: True if a cheaper model passed ≥70% of tasks
        suggested_model: cheaper model if model_over_spec is True
        redundant_tool_calls: count of duplicate tool call pairs
        retry_storms_detected: count of unnecessary retry sequences
        has_parallelizable_calls: True if sequential calls could be parallelised
    """

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
    """JSON contract for check #3 output (security_result.json).

    Fields:
        is_safe: overall verdict
        critical_count: number of Critical findings
        high_count: number of High findings
        medium_count: number of Medium findings
        low_count: number of Low findings
        finding_ids: list of finding identifiers (for deduplication)
        hardcoded_secrets: True if static scan found embedded credentials
        prompt_injection_vulnerable: True if adversarial probing succeeded
        unsafe_deserialization: True if pickle/eval/yaml.load detected
    """

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
    """Outcome of the dominance check for a single candidate."""

    candidate_id: str
    dominates: bool

    # Per-axis delta as a signed percentage (positive = improvement)
    reliability_delta_pct: Optional[float] = None
    cost_delta_pct: Optional[float] = None
    complexity_delta_pct: Optional[float] = None
    security_delta_pct: Optional[float] = None

    winning_axes: list[str] = Field(default_factory=list)
    regressed_axes: list[str] = Field(default_factory=list)

    reason: str = ""


class AlternativeCandidate(BaseModel):
    """A single KB entry, enriched with dominance analysis."""

    id: str
    name: str
    recommendation_type: RecommendationType
    description: str = ""

    kb_metrics: AlternativeMetrics
    dominance: Optional[DominanceResult] = None

    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    code_example: Optional[str] = None
    evidence_url: Optional[str] = None


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
