"""Smoke test: run_efficiency loads agent from path and writes JSON contract."""

from pathlib import Path

from agentcheck.alternatives.models import WastefulnessResult
from agentcheck.efficiency import run_efficiency


def test_run_efficiency_writes_wastefulness_json(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_efficiency(
        fixture_agent_path,
        fixture_results_dir,
        task_prompt="Plan a 1-day trip to Tokyo.",
    )

    assert isinstance(result, WastefulnessResult)
    out = fixture_results_dir / "wastefulness_result.json"
    assert out.exists()
    parsed = WastefulnessResult.model_validate_json(out.read_text())
    assert 0.0 <= parsed.waste_score <= 100.0

    # The execution log must land in results_dir, NOT the cwd
    assert (fixture_results_dir / "execution_log.json").exists()
    assert not Path("execution_log.json").exists()
