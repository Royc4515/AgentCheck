from __future__ import annotations

"""OverallScorer — synthesises check #1/#2/#3 results into a single grade.

Weights:
    Reliability  40 %  (task completion rate from check #1)
    Efficiency   30 %  (inverted waste_score from check #2)
    Security     30 %  (finding-severity score from check #3)

If a check's JSON was absent, that axis is excluded and the remaining
axes are re-weighted proportionally so the grade is always honest about
what data it had.
"""

from typing import Optional

from .models import AgentProfile, LetterGrade, OverallScore

# Weights — must sum to 1.0
_WEIGHTS = {
    "reliability": 0.40,
    "efficiency":  0.30,
    "security":    0.30,
}


class OverallScorer:
    """Computes an OverallScore from an AgentProfile."""

    def score(self, profile: AgentProfile) -> OverallScore:
        axes: dict[str, float] = {}

        reliability = _reliability_score(profile)
        if reliability is not None:
            axes["reliability"] = reliability

        efficiency = _efficiency_score(profile)
        if efficiency is not None:
            axes["efficiency"] = efficiency

        security = _security_score(profile)
        if security is not None:
            axes["security"] = security

        overall = _weighted_average(axes) if axes else None

        return OverallScore(
            reliability_score=axes.get("reliability"),
            efficiency_score=axes.get("efficiency"),
            security_score=axes.get("security"),
            reliability_grade=_grade(axes.get("reliability")),
            efficiency_grade=_grade(axes.get("efficiency")),
            security_grade=_grade(axes.get("security")),
            overall_score=overall,
            overall_grade=_grade(overall),
            axes_available=list(axes.keys()),
        )


# ---------------------------------------------------------------------------
# Per-axis normalisers (all return 0–100, higher = better)
# ---------------------------------------------------------------------------

def _reliability_score(profile: AgentProfile) -> Optional[float]:
    rate = profile.task_completion_rate
    if rate is None:
        return None
    return round(rate * 100, 1)


def _efficiency_score(profile: AgentProfile) -> Optional[float]:
    if profile.wastefulness is None:
        return None
    # waste_score is 0 (perfect) → 100 (catastrophic); invert it
    return round(100.0 - profile.wastefulness.waste_score, 1)


def _security_score(profile: AgentProfile) -> Optional[float]:
    sec = profile.security
    if sec is None:
        return None

    # Deduct points per finding severity
    deductions = (
        sec.critical_count * 30
        + sec.high_count    * 15
        + sec.medium_count  *  5
        + sec.low_count     *  2
    )
    return round(max(0.0, 100.0 - deductions), 1)


def _weighted_average(axes: dict[str, float]) -> float:
    total_weight = sum(_WEIGHTS[ax] for ax in axes)
    weighted_sum = sum(_WEIGHTS[ax] * score for ax, score in axes.items())
    return round(weighted_sum / total_weight, 1)


def _grade(score: Optional[float]) -> Optional[LetterGrade]:
    if score is None:
        return None
    if score >= 90:
        return LetterGrade.A
    if score >= 80:
        return LetterGrade.B
    if score >= 70:
        return LetterGrade.C
    if score >= 60:
        return LetterGrade.D
    return LetterGrade.F
