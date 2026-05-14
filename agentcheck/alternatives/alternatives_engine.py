from __future__ import annotations

"""AlternativesEngine — the single entry point for check #4.

Two modes:

  KB mode (default)::

      engine = AlternativesEngine()
      report = engine.run()
      # Uses KB-projected metrics for the alternatives.

  Empirical mode::

      engine = AlternativesEngine(empirical=True, tasks_path=Path("tasks.yaml"))
      report = engine.run()
      # Generates each alternative agent, runs checks #1/#2/#3 on it
      # (StubCheckRunner now — swap for RealCheckRunner when checks land).
"""

import datetime
from pathlib import Path
from typing import Optional

from .check_runner import CheckRunner, StubCheckRunner
from .kb_loader import load_kb
from .matching_engine import MatchingEngine
from .models import (
    AgentProfile,
    AlternativeCandidate,
    CandidateComparison,
    FullComparisonReport,
    ValidationResult,
)
from .profile_loader import AgentProfileLoader
from .scorer import OverallScorer
from .validation import LLMAgentGenerator, ValidationPipeline


class AlternativesEngine:
    """Orchestrates the full check #4 pipeline.

    Parameters
    ----------
    results_dir:
        Directory containing the check #1/#2/#3 JSON files.
        Defaults to ``.agentcheck/``.
    strict:
        If True, missing JSON files raise an error.
    candidates:
        Override the KB candidates list (mainly for testing).
    empirical:
        If True, generate each alternative agent and run checks #1/#2/#3
        on it to get real comparison data instead of KB projections.
    tasks_path:
        Path to the task battery YAML — required when empirical=True.
    runner:
        CheckRunner used in empirical mode.
        Defaults to StubCheckRunner.
        Swap for RealCheckRunner when checks #1/#2/#3 are implemented.
    """

    def __init__(
        self,
        results_dir: Optional[Path] = None,
        strict: bool = False,
        candidates: Optional[list[AlternativeCandidate]] = None,
        empirical: bool = False,
        tasks_path: Optional[Path] = None,
        runner: Optional[CheckRunner] = None,
    ) -> None:
        self._loader = AgentProfileLoader(results_dir=results_dir, strict=strict)
        kb = candidates if candidates is not None else load_kb()
        self._matching = MatchingEngine(candidates=kb)
        self._empirical = empirical
        self._tasks_path = tasks_path
        self._pipeline = ValidationPipeline(
            generator=LLMAgentGenerator(),
            runner=runner or StubCheckRunner(),
        )
        self._scorer = OverallScorer()

    def run(self) -> FullComparisonReport:
        profile = self._loader.load()
        return self.run_with_profile(profile)

    def run_with_profile(self, profile: AgentProfile) -> FullComparisonReport:
        top3 = self._matching.top3(profile)

        if self._empirical:
            comparisons, validations = self._run_empirical(profile, top3)
        else:
            comparisons = [_kb_comparison(profile, c) for c in top3]
            validations = []

        return FullComparisonReport(
            agent_profile=profile,
            overall_score=self._scorer.score(profile),
            comparisons=comparisons,
            validation_results=validations,
            kb_snapshot_date=datetime.date.today().isoformat(),
            total_candidates_evaluated=len(self._matching._candidates),
        )

    # ------------------------------------------------------------------

    def _run_empirical(
        self,
        profile: AgentProfile,
        candidates: list[AlternativeCandidate],
    ) -> tuple[list[CandidateComparison], list[ValidationResult]]:
        if not self._tasks_path:
            raise ValueError("tasks_path is required for empirical mode.")

        comparisons: list[CandidateComparison] = []
        validations: list[ValidationResult] = []

        for candidate in candidates:
            vr = self._pipeline.validate(profile, candidate, self._tasks_path)
            validations.append(vr)
            comparisons.append(_empirical_comparison(profile, candidate, vr))

        return comparisons, validations


# ---------------------------------------------------------------------------
# Comparison builders
# ---------------------------------------------------------------------------

def _kb_comparison(
    profile: AgentProfile,
    candidate: AlternativeCandidate,
) -> CandidateComparison:
    """Build comparison using KB-projected metrics."""
    return CandidateComparison(
        candidate=candidate,
        original_reliability=profile.task_completion_rate,
        original_cost=profile.cost_per_task_usd,
        original_loc=profile.loc,
        original_security_findings=profile.security_finding_count,
        alt_reliability=candidate.kb_metrics.reliability_score,
        alt_cost=candidate.kb_metrics.cost_per_task_usd,
        alt_loc=candidate.kb_metrics.loc_estimate,
        alt_security_findings=candidate.kb_metrics.security_finding_count,
    )


def _empirical_comparison(
    profile: AgentProfile,
    candidate: AlternativeCandidate,
    vr: ValidationResult,
) -> CandidateComparison:
    """Build comparison using real empirical results from check runs."""
    return CandidateComparison(
        candidate=candidate,
        original_reliability=profile.task_completion_rate,
        original_cost=profile.cost_per_task_usd,
        original_loc=profile.loc,
        original_security_findings=profile.security_finding_count,
        # Real numbers — not KB projections
        alt_reliability=vr.task_completion_rate,
        alt_cost=vr.cost_per_task_usd,
        alt_loc=None,       # LOC not yet in ValidationResult; add when check #1 exposes it
        alt_security_findings=None,  # add when check #3 exposes it via ValidationResult
    )
