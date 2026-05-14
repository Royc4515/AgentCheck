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

# --- Dominance thresholds (SDD v0.4 §2) ---
_RELIABILITY_WIN_THRESHOLD = 0.10    # +10 pp completion rate
_COST_WIN_THRESHOLD = 0.30           # -30 % cost
_COMPLEXITY_WIN_THRESHOLD = 0.40     # -40 % LOC
_REGRESSION_GUARD = 0.15             # no axis may regress more than 15 %

# Security: alternative wins if it has strictly fewer findings
# (can't express as a % because original may have 0)
_SECURITY_WIN_MIN_REDUCTION = 1      # must eliminate at least 1 finding

_TOP_N = 3  # maximum candidates returned by top3()

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
        security_delta: Optional[float] = None

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
            delta = (cur_cost - alt_cost) / cur_cost  # positive = cheaper
            cost_delta = round(delta * 100, 2)

            if delta >= _COST_WIN_THRESHOLD:
                winning_axes.append("cost")
            elif delta < -_REGRESSION_GUARD:
                regressed_axes.append("cost")

        # --- Complexity axis (LOC proxy) ---
        if profile.loc is not None and profile.loc > 0:
            alt_loc = candidate.kb_metrics.loc_estimate
            cur_loc = profile.loc
            delta = (cur_loc - alt_loc) / cur_loc  # positive = simpler
            complexity_delta = round(delta * 100, 2)

            if delta >= _COMPLEXITY_WIN_THRESHOLD:
                winning_axes.append("complexity")
            elif delta < -_REGRESSION_GUARD:
                regressed_axes.append("complexity")

        # --- Security axis ---
        if profile.security_finding_count is not None:
            cur_sec = profile.security_finding_count
            alt_sec = candidate.kb_metrics.security_finding_count

            if cur_sec > 0:
                delta = (cur_sec - alt_sec) / cur_sec  # positive = safer
                security_delta = round(delta * 100, 2)
                if (cur_sec - alt_sec) >= _SECURITY_WIN_MIN_REDUCTION:
                    winning_axes.append("security")
                elif delta < -_REGRESSION_GUARD:
                    regressed_axes.append("security")
            elif alt_sec == 0:
                # both clean — neutral, no win, no regression
                security_delta = 0.0
            else:
                # original clean, alternative has findings → regression
                regressed_axes.append("security")
                security_delta = -100.0

        dominates = len(winning_axes) > 0 and len(regressed_axes) == 0

        return DominanceResult(
            candidate_id=candidate.id,
            dominates=dominates,
            reliability_delta_pct=reliability_delta,
            cost_delta_pct=cost_delta,
            complexity_delta_pct=complexity_delta,
            security_delta_pct=security_delta,
            winning_axes=winning_axes,
            regressed_axes=regressed_axes,
            reason=_build_reason(dominates, winning_axes, regressed_axes),
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
        top3 = engine.top3(profile)
    """

    def __init__(self, candidates: Optional[list[AlternativeCandidate]] = None) -> None:
        self._candidates = candidates if candidates is not None else load_kb()
        self._checker = DominanceChecker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rank(self, profile: AgentProfile) -> list[AlternativeCandidate]:
        """Return ALL eligible KB candidates ranked best-first."""
        scored = [
            sc for c in self._candidates
            if (sc := self._evaluate(profile, c)) is not None
        ]
        scored.sort(key=lambda s: (-int(s.dominance.dominates), -s.composite_score))
        return [s.candidate for s in scored]

    def top3(self, profile: AgentProfile) -> list[AlternativeCandidate]:
        """Return the top 3 candidates (or fewer if KB has fewer qualifying entries)."""
        return self.rank(profile)[:_TOP_N]

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
        # Never recommend the framework the agent already uses
        if (
            candidate.recommendation_type == RecommendationType.FRAMEWORK_SHIFT
            and profile.framework
            and candidate.id == profile.framework.lower().replace("-", "_")
        ):
            return False

        # delete_the_llm only when the task is genuinely deterministic
        if candidate.recommendation_type == RecommendationType.DELETE_THE_LLM:
            if not _DETERMINISTIC_PATTERNS.intersection(set(profile.detected_patterns)):
                return False

        # Stale KB entries lose trust
        if candidate.freshness_score < 0.5:
            return False

        return True

    @staticmethod
    def _composite_score(dominance: DominanceResult, freshness: float) -> float:
        base = 0.0
        if dominance.cost_delta_pct is not None:
            base += max(0.0, dominance.cost_delta_pct) * 0.40
        if dominance.reliability_delta_pct is not None:
            base += max(0.0, dominance.reliability_delta_pct) * 0.30
        if dominance.complexity_delta_pct is not None:
            base += max(0.0, dominance.complexity_delta_pct) * 0.20
        if dominance.security_delta_pct is not None:
            base += max(0.0, dominance.security_delta_pct) * 0.10
        return round(base * freshness, 4)
