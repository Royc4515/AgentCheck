"""AgentCheck v0.4 — Alternatives check."""

from .alternatives_engine import AlternativesEngine
from .matching_engine import MatchingEngine
from .models import (
    AgentProfile,
    AlternativeCandidate,
    AlternativeMetrics,
    AlternativesReport,
    CandidateComparison,
    DetectedPattern,
    DominanceResult,
    FullComparisonReport,
    RecommendationType,
    ReliabilityResult,
    SecurityResult,
    ValidationResult,
    ValidationStatus,
    WastefulnessResult,
)
from .profile_loader import AgentProfileLoader, CheckResultNotFound
from .reporter import AlternativesReporter
from .check_runner import CheckRunner, RealCheckRunner, StubCheckRunner
from .validation import (
    BatteryRunner,
    FairnessGuard,
    FairnessViolation,
    LLMAgentGenerator,
    ValidationPipeline,
)

__all__ = [
    "CheckRunner",
    "RealCheckRunner",
    "StubCheckRunner",
    "AgentProfile",
    "AgentProfileLoader",
    "AlternativeCandidate",
    "AlternativeMetrics",
    "AlternativesEngine",
    "AlternativesReport",
    "AlternativesReporter",
    "BatteryRunner",
    "CandidateComparison",
    "CheckResultNotFound",
    "DetectedPattern",
    "DominanceResult",
    "FairnessGuard",
    "FairnessViolation",
    "FullComparisonReport",
    "LLMAgentGenerator",
    "MatchingEngine",
    "RecommendationType",
    "ReliabilityResult",
    "SecurityResult",
    "ValidationPipeline",
    "ValidationResult",
    "ValidationStatus",
    "WastefulnessResult",
]
