from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import yaml

from .models import AlternativeCandidate, AlternativeMetrics, RecommendationType

_KB_ROOT = Path(__file__).parent / "kb"

_TYPE_MAP: dict[str, RecommendationType] = {
    "framework": RecommendationType.FRAMEWORK_SHIFT,
    "pattern": RecommendationType.PATTERN_SHIFT,
    "architectural_shift": RecommendationType.ARCHITECTURAL_SHIFT,
}

_FRESHNESS_DECAY_DAYS = 90  # entries older than this start losing trust


def _freshness(snapshot_date_str: str) -> float:
    """Returns 1.0 for a fresh snapshot, decaying linearly to 0.5 at 90 days.

    Accepts both full ISO dates ("2026-05-01") and partial month strings ("2026-05").
    """
    try:
        # Normalise "YYYY-MM" → "YYYY-MM-01" before parsing
        if len(snapshot_date_str) == 7:
            snapshot_date_str = snapshot_date_str + "-01"
        snapshot = datetime.date.fromisoformat(snapshot_date_str)
        age_days = (datetime.date.today() - snapshot).days
        if age_days <= 0:
            return 1.0
        return max(0.5, 1.0 - (age_days / _FRESHNESS_DECAY_DAYS) * 0.5)
    except (ValueError, TypeError):
        return 0.7


def _rec_type(raw: dict[str, Any]) -> RecommendationType:
    entry_type = raw.get("type", "")
    if raw.get("id") == "delete_the_llm":
        return RecommendationType.DELETE_THE_LLM
    if raw.get("id") == "model_downgrade":
        return RecommendationType.MODEL_DOWNGRADE
    return _TYPE_MAP.get(entry_type, RecommendationType.ARCHITECTURAL_SHIFT)


def _metrics_from(raw: dict[str, Any]) -> AlternativeMetrics:
    m = raw.get("metrics", {})
    return AlternativeMetrics(
        reliability_score=float(m.get("reliability_score", 0.75)),
        cost_per_task_usd=float(m.get("cost_per_task_usd", 0.05)),
        loc_estimate=int(m.get("loc_estimate", 100)),
        cyclomatic_complexity=int(m.get("cyclomatic_complexity", 15)),
    )


def _code_example(raw: dict[str, Any]) -> str | None:
    example = raw.get("example_replacement")
    if not example:
        return None
    after = example.get("after", "")
    desc = example.get("description", "")
    return f"# {desc}\n{after}".strip() if after else None


def load_kb() -> list[AlternativeCandidate]:
    """Load every YAML file in the KB directory tree into AlternativeCandidate objects."""
    candidates: list[AlternativeCandidate] = []

    for yaml_path in sorted(_KB_ROOT.rglob("*.yaml")):
        raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

        candidate = AlternativeCandidate(
            id=raw.get("id", yaml_path.stem),
            name=raw.get("name", yaml_path.stem),
            recommendation_type=_rec_type(raw),
            description=str(raw.get("description", "")),
            kb_metrics=_metrics_from(raw),
            freshness_score=_freshness(str(raw.get("snapshot_date", ""))),
            strengths=list(raw.get("strengths", [])),
            weaknesses=list(raw.get("weaknesses", [])),
            code_example=_code_example(raw),
            evidence_url=raw.get("evidence_url"),
        )
        candidates.append(candidate)

    return candidates
