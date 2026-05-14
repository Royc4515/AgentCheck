"""AgentCheck v0.4 — Alternatives check.

Main pipeline entry point::

    from agentcheck.alternatives import run
    from pathlib import Path

    report = run(results_dir=Path(".agentcheck"))

``run()`` expects the three JSON files written by checks #1, #2, #3 to
already exist inside ``results_dir``:
  - reliability_result.json   (check #1)
  - wastefulness_result.json  (check #2)
  - security_result.json      (check #3)

It returns a ``FullComparisonReport`` with an overall A–F grade and the top
real-world alternative frameworks/patterns from the knowledge base.
"""

from pathlib import Path
from typing import Literal, Optional

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


def run(
    results_dir: Optional[Path] = None,
    strict: bool = False,
    output_mode: Literal["terminal", "json", "summary"] = "terminal",
) -> FullComparisonReport:
    """Run check #4 and return the full comparison report.

    This is the canonical entry point for the main AgentCheck pipeline.
    Call it after checks #1, #2, and #3 have written their JSON files.

    Parameters
    ----------
    results_dir:
        Directory containing the check JSON files. Defaults to ``.agentcheck/``
        in the current working directory.
    strict:
        If True, raises ``CheckResultNotFound`` when any JSON file is missing.
        If False (default), missing files are silently skipped and the report
        is built from whatever data is available.
    output_mode:
        Controls what ``AlternativesReporter`` prints to the terminal.
        Pass ``"json"`` for machine-readable output, ``"summary"`` for a
        single CI-friendly line. The rendered string is also returned by the
        reporter but the report object is always returned by this function
        regardless of mode.

    Returns
    -------
    FullComparisonReport
        Contains the overall A–F score and up to 3 suggested alternatives.
    """
    engine = AlternativesEngine(results_dir=results_dir, strict=strict)
    report = engine.run()
    AlternativesReporter(mode=output_mode).render(report)
    return report


__all__ = [
    "run",
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
