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
    LetterGrade,
    OverallScore,
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
from .scorer import OverallScorer
from .validation import BatteryRunner

__all__ = [
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
    "CheckRunner",
    "DetectedPattern",
    "DominanceResult",
    "FullComparisonReport",
    "LetterGrade",
    "MatchingEngine",
    "OverallScore",
    "OverallScorer",
    "RealCheckRunner",
    "RecommendationType",
    "ReliabilityResult",
    "SecurityResult",
    "StubCheckRunner",
    "ValidationResult",
    "ValidationStatus",
    "WastefulnessResult",
]
