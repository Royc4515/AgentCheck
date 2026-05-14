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


class AgentProfile(BaseModel):
    """Snapshot of the audited agent's observable characteristics.

    Produced by combining static analysis (AST scan) with v0.1 / v0.2 run
    outputs.  Any field that cannot be determined is left as None; the
    MatchingEngine degrades gracefully on sparse profiles.
    """

    framework: Optional[str] = None
    framework_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    model_id: Optional[str] = None
    detected_patterns: list[DetectedPattern] = Field(default_factory=list)

    # v0.1 outputs
    task_completion_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # v0.2 outputs
    cost_per_task_usd: Optional[float] = Field(default=None, ge=0.0)
    loc: Optional[int] = Field(default=None, ge=0)
    cyclomatic_complexity: Optional[int] = Field(default=None, ge=0)
    waste_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    @field_validator("framework_confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        return round(v, 4)


class AlternativeMetrics(BaseModel):
    """Projected metrics for a KB candidate."""

    reliability_score: float = Field(ge=0.0, le=1.0)
    cost_per_task_usd: float = Field(ge=0.0)
    loc_estimate: int = Field(ge=0)
    cyclomatic_complexity: int = Field(ge=0)


class DominanceResult(BaseModel):
    """Outcome of the dominance check for a single candidate."""

    candidate_id: str
    dominates: bool

    # Per-axis delta as a signed percentage (positive = improvement)
    reliability_delta_pct: Optional[float] = None
    cost_delta_pct: Optional[float] = None
    complexity_delta_pct: Optional[float] = None

    # Which axis triggered the "better" threshold
    winning_axes: list[str] = Field(default_factory=list)
    # Which axes (if any) regressed beyond the 15 % guard
    regressed_axes: list[str] = Field(default_factory=list)

    reason: str = ""


class AlternativeCandidate(BaseModel):
    """A single entry from the KB, enriched with dominance analysis."""

    id: str
    name: str
    recommendation_type: RecommendationType
    description: str = ""

    kb_metrics: AlternativeMetrics
    dominance: Optional[DominanceResult] = None

    # Confidence that the KB data is still current (decays with snapshot age)
    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)

    # Optional concrete code snippet shown in the report
    code_example: Optional[str] = None
    evidence_url: Optional[str] = None


class ValidationStatus(str, Enum):
    NOT_RUN = "not_run"
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class ValidationResult(BaseModel):
    """Result of the --validate-alternative empirical run."""

    candidate_id: str
    status: ValidationStatus = ValidationStatus.NOT_RUN

    generated_agent_path: Optional[str] = None
    task_completion_rate: Optional[float] = None
    cost_per_task_usd: Optional[float] = None

    confirmed_dominates: Optional[bool] = None
    error_message: Optional[str] = None


class AlternativesReport(BaseModel):
    """Top-level output of the Alternatives check."""

    agent_profile: AgentProfile
    ranked_candidates: list[AlternativeCandidate] = Field(default_factory=list)
    validation_results: list[ValidationResult] = Field(default_factory=list)

    kb_snapshot_date: str = ""
    total_candidates_evaluated: int = 0

    @property
    def top_recommendation(self) -> Optional[AlternativeCandidate]:
        for c in self.ranked_candidates:
            if c.dominance and c.dominance.dominates:
                return c
        return None

    @property
    def has_actionable_recommendation(self) -> bool:
        return self.top_recommendation is not None
