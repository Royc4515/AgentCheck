from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .kb_loader import load_kb
from .models import (
    AgentProfile,
    AlternativeCandidate,
    DetectedPattern,
    DominanceResult,
    RecommendationType,
)

# --- Dominance thresholds (from SDD v0.4 §2) ---
_RELIABILITY_WIN_THRESHOLD = 0.10    # +10 pp completion rate
_COST_WIN_THRESHOLD = 0.30           # -30 % cost
_COMPLEXITY_WIN_THRESHOLD = 0.40     # -40 % LOC / cyclomatic
_REGRESSION_GUARD = 0.15             # no axis may regress more than 15 %

# Patterns that strongly suggest the LLM can be deleted
_DETERMINISTIC_PATTERNS = {
    DetectedPattern.DETERMINISTIC_TRANSFORM,
    DetectedPattern.SIMPLE_EXTRACTION,
}


@dataclass
class _ScoredCandidate:
    candidate: AlternativeCandidate
    dominance: DominanceResult
    composite_score: float = 0.0


class DominanceChecker:
    """Evaluates whether a KB candidate dominates the current agent profile."""

    def check(
        self,
        profile: AgentProfile,
        candidate: AlternativeCandidate,
    ) -> DominanceResult:
        winning_axes: list[str] = []
        regressed_axes: list[str] = []

        reliability_delta: Optional[float] = None
        cost_delta: Optional[float] = None
        complexity_delta: Optional[float] = None

        # --- Reliability axis ---
        if profile.task_completion_rate is not None:
            alt_rel = candidate.kb_metrics.reliability_score
            cur_rel = profile.task_completion_rate
            delta = (alt_rel - cur_rel) / max(cur_rel, 1e-9)
            reliability_delta = round(delta * 100, 2)

            if delta >= _RELIABILITY_WIN_THRESHOLD:
                winning_axes.append("reliability")
            elif delta < -_REGRESSION_GUARD:
                regressed_axes.append("reliability")

        # --- Cost axis ---
        if profile.cost_per_task_usd is not None and profile.cost_per_task_usd > 0:
            alt_cost = candidate.kb_metrics.cost_per_task_usd
            cur_cost = profile.cost_per_task_usd
            # cost delta: positive means the alternative is cheaper
            delta = (cur_cost - alt_cost) / cur_cost
            cost_delta = round(delta * 100, 2)

            if delta >= _COST_WIN_THRESHOLD:
                winning_axes.append("cost")
            elif delta < -_REGRESSION_GUARD:
                # alternative is more expensive — not a regression per SDD,
                # but flag it so the report is honest
                regressed_axes.append("cost")

        # --- Complexity axis (LOC proxy) ---
        if profile.loc is not None and profile.loc > 0:
            alt_loc = candidate.kb_metrics.loc_estimate
            cur_loc = profile.loc
            delta = (cur_loc - alt_loc) / cur_loc
            complexity_delta = round(delta * 100, 2)

            if delta >= _COMPLEXITY_WIN_THRESHOLD:
                winning_axes.append("complexity")
            elif delta < -_REGRESSION_GUARD:
                regressed_axes.append("complexity")

        dominates = len(winning_axes) > 0 and len(regressed_axes) == 0

        reason = _build_reason(dominates, winning_axes, regressed_axes)

        return DominanceResult(
            candidate_id=candidate.id,
            dominates=dominates,
            reliability_delta_pct=reliability_delta,
            cost_delta_pct=cost_delta,
            complexity_delta_pct=complexity_delta,
            winning_axes=winning_axes,
            regressed_axes=regressed_axes,
            reason=reason,
        )


def _build_reason(
    dominates: bool,
    winning: list[str],
    regressed: list[str],
) -> str:
    if dominates:
        axes = " and ".join(winning)
        return f"Dominates on {axes} with no regressions."
    if regressed:
        axes = " and ".join(regressed)
        return f"Blocked by regression guard: {axes} regresses > 15 %."
    return "No axis clears the improvement threshold."


class MatchingEngine:
    """Filters the KB, scores each candidate, and returns a ranked list.

    Usage::

        engine = MatchingEngine()
        report_candidates = engine.rank(profile)
    """

    def __init__(self, candidates: Optional[list[AlternativeCandidate]] = None) -> None:
        self._candidates = candidates if candidates is not None else load_kb()
        self._checker = DominanceChecker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank(self, profile: AgentProfile) -> list[AlternativeCandidate]:
        """Return KB candidates ranked best-first, with dominance analysis attached."""
        scored = [
            sc for c in self._candidates
            if (sc := self._evaluate(profile, c)) is not None
        ]
        scored.sort(key=lambda s: (-int(s.dominance.dominates), -s.composite_score))
        return [s.candidate for s in scored]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        profile: AgentProfile,
        candidate: AlternativeCandidate,
    ) -> Optional[_ScoredCandidate]:
        if not self._is_eligible(profile, candidate):
            return None

        dominance = self._checker.check(profile, candidate)
        candidate.dominance = dominance

        score = self._composite_score(dominance, candidate.freshness_score)
        return _ScoredCandidate(candidate=candidate, dominance=dominance, composite_score=score)

    def _is_eligible(self, profile: AgentProfile, candidate: AlternativeCandidate) -> bool:
        """Pre-filter: skip candidates that are obviously a bad fit."""

        # Never recommend the same framework the agent already uses
        if (
            candidate.recommendation_type == RecommendationType.FRAMEWORK_SHIFT
            and profile.framework
            and candidate.id == profile.framework.lower().replace("-", "_")
        ):
            return False

        # Only suggest delete_the_llm if the agent's patterns qualify
        if candidate.recommendation_type == RecommendationType.DELETE_THE_LLM:
            if not _DETERMINISTIC_PATTERNS.intersection(set(profile.detected_patterns)):
                return False

        # Skip stale KB entries (freshness < 0.5 means snapshot is very old)
        if candidate.freshness_score < 0.5:
            return False

        return True

    @staticmethod
    def _composite_score(dominance: DominanceResult, freshness: float) -> float:
        """Higher is better. Winning axes each contribute; freshness is a multiplier."""
        base = 0.0
        if dominance.cost_delta_pct is not None:
            base += max(0.0, dominance.cost_delta_pct) * 0.5
        if dominance.reliability_delta_pct is not None:
            base += max(0.0, dominance.reliability_delta_pct) * 0.3
        if dominance.complexity_delta_pct is not None:
            base += max(0.0, dominance.complexity_delta_pct) * 0.2
        return round(base * freshness, 4)
