from __future__ import annotations

"""AlternativesEngine — the single entry point for check #4.

Typical usage::

    engine = AlternativesEngine()
    report = engine.run()          # reads .agentcheck/*.json automatically
    print(report.top_recommendation)

Or with explicit paths::

    engine = AlternativesEngine(results_dir=Path("./my_run"))
    report = engine.run()
"""

import datetime
from pathlib import Path
from typing import Optional

from .kb_loader import load_kb
from .matching_engine import MatchingEngine
from .models import (
    AgentProfile,
    AlternativeCandidate,
    CandidateComparison,
    FullComparisonReport,
)
from .profile_loader import AgentProfileLoader


class AlternativesEngine:
    """Orchestrates the full check #4 pipeline:

        1. Load AgentProfile from check #1/#2/#3 JSON files
        2. Find top 3 candidates from KB
        3. Build a FullComparisonReport (original vs each alternative)

    Parameters
    ----------
    results_dir:
        Directory containing reliability_result.json, wastefulness_result.json,
        security_result.json. Defaults to ``.agentcheck/``.
    strict:
        Passed to AgentProfileLoader. If True, missing JSON files raise an error.
    candidates:
        Override the KB candidates list (mainly for testing).
    """

    def __init__(
        self,
        results_dir: Optional[Path] = None,
        strict: bool = False,
        candidates: Optional[list[AlternativeCandidate]] = None,
    ) -> None:
        self._loader = AgentProfileLoader(results_dir=results_dir, strict=strict)
        kb = candidates if candidates is not None else load_kb()
        self._engine = MatchingEngine(candidates=kb)

    def run(self) -> FullComparisonReport:
        profile = self._loader.load()
        return self.run_with_profile(profile)

    def run_with_profile(self, profile: AgentProfile) -> FullComparisonReport:
        """Run matching against a pre-built profile (useful when caller already
        has check results in memory rather than on disk)."""
        top3 = self._engine.top3(profile)
        comparisons = [_build_comparison(profile, c) for c in top3]

        return FullComparisonReport(
            agent_profile=profile,
            comparisons=comparisons,
            kb_snapshot_date=datetime.date.today().isoformat(),
            total_candidates_evaluated=len(self._engine._candidates),
        )


def _build_comparison(
    profile: AgentProfile,
    candidate: AlternativeCandidate,
) -> CandidateComparison:
    return CandidateComparison(
        candidate=candidate,
        # Original values
        original_reliability=profile.task_completion_rate,
        original_cost=profile.cost_per_task_usd,
        original_loc=profile.loc,
        original_security_findings=profile.security_finding_count,
        # KB-projected values
        alt_reliability=candidate.kb_metrics.reliability_score,
        alt_cost=candidate.kb_metrics.cost_per_task_usd,
        alt_loc=candidate.kb_metrics.loc_estimate,
        alt_security_findings=candidate.kb_metrics.security_finding_count,
    )
