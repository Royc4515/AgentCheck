"""Smoke test: run_quality consumes an agent path and writes a JSON contract."""

import json
from pathlib import Path

from agentcheck.shared.models import ReliabilityResult
from agentcheck.quality import run_quality


def test_run_quality_writes_reliability_json(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_quality(fixture_agent_path, fixture_results_dir)

    assert isinstance(result, ReliabilityResult)
    out = fixture_results_dir / "reliability_result.json"
    assert out.exists()
    parsed = ReliabilityResult.model_validate_json(out.read_text())
    assert parsed.tasks_total >= 1
    assert parsed.loc is not None and parsed.loc > 0


def test_run_quality_accepts_path_object(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    # Path-flow check: pass a Path, not a string
    result = run_quality(Path(fixture_agent_path), fixture_results_dir)
    assert result.tasks_total >= 1
