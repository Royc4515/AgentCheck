from __future__ import annotations

"""AlternativesEngine — the single entry point for check #4.

KB mode (the only mode)::

    engine = AlternativesEngine()
    report = engine.run()

Check #4 reads the JSON output files from checks #1, #2, #3, computes an
overall health score (A–F), then surfaces the top 3 real-world alternative
frameworks / patterns from the YAML knowledge base — complete with documented
pros, cons, and evidence links.

No agent code is generated.  Alternatives are pointers to real, existing
tools (PydanticAI, AutoGen, Raw SDK, etc.) with KB-projected metrics.
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
from .scorer import OverallScorer


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
    """

    def __init__(
        self,
        results_dir: Optional[Path] = None,
        strict: bool = False,
        candidates: Optional[list[AlternativeCandidate]] = None,
    ) -> None:
        self._loader = AgentProfileLoader(results_dir=results_dir, strict=strict)
        kb = candidates if candidates is not None else load_kb()
        self._matching = MatchingEngine(candidates=kb)
        self._scorer = OverallScorer()

    def run(self) -> FullComparisonReport:
        profile = self._loader.load()
        return self.run_with_profile(profile)

    def run_with_profile(self, profile: AgentProfile) -> FullComparisonReport:
        top3 = self._matching.top3(profile)
        comparisons = [_kb_comparison(profile, c) for c in top3]

        return FullComparisonReport(
            agent_profile=profile,
            overall_score=self._scorer.score(profile),
            comparisons=comparisons,
            validation_results=[],
            kb_snapshot_date=datetime.date.today().isoformat(),
            total_candidates_evaluated=len(self._matching._candidates),
        )


# ---------------------------------------------------------------------------
# Comparison builder
# ---------------------------------------------------------------------------

def _kb_comparison(
    profile: AgentProfile,
    candidate: AlternativeCandidate,
) -> CandidateComparison:
    """Build a side-by-side comparison using KB-projected metrics."""
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
