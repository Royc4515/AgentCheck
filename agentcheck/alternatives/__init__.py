"""AgentCheck v0.4 — Alternatives check."""

from .matching_engine import MatchingEngine
from .models import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    AlternativesReport,
    DetectedPattern,
    DominanceResult,
    RecommendationType,
    ValidationResult,
    ValidationStatus,
)
from .reporter import AlternativesReporter
from .validation import (
    BatteryRunner,
    FairnessGuard,
    FairnessViolation,
    LLMAgentGenerator,
    ValidationPipeline,
)

__all__ = [
    "AgentProfile",
    "AlternativeCandidate",
    "AlternativeMetrics",
    "AlternativesReport",
    "AlternativesReporter",
    "BatteryRunner",
    "DetectedPattern",
    "DominanceResult",
    "FairnessGuard",
    "FairnessViolation",
    "LLMAgentGenerator",
    "MatchingEngine",
    "RecommendationType",
    "ValidationPipeline",
    "ValidationResult",
    "ValidationStatus",
]
