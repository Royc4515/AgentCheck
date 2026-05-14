"""Tests for StubCheckRunner — the test double for check #1/#2/#3 runners.

The empirical agent-generation pipeline (generate → fairness-guard → run checks)
has been removed from check #4.  Check #4 operates in KB-only mode.
These tests cover the StubCheckRunner that remains as the wiring point for
future integration with real check implementations.
"""

from pathlib import Path

import pytest

from agentcheck.alternatives import (
    StubCheckRunner,
)


class TestStubCheckRunner:
    def test_returns_reliability_result(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(task_completion_rate=0.85)
        result = runner.run_reliability(tmp_path / "agent.py", tmp_path / "tasks.yaml")
        assert result.task_completion_rate == pytest.approx(0.85)

    def test_returns_wastefulness_result(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(cost_per_task_usd=0.020)
        result = runner.run_wastefulness(tmp_path / "agent.py", tmp_path / "tasks.yaml")
        assert result.cost_per_task_usd == pytest.approx(0.020)

    def test_returns_security_result_clean(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(security_critical=0, security_high=0)
        result = runner.run_security(tmp_path / "agent.py")
        assert result.is_safe is True
        assert result.total_findings == 0

    def test_returns_security_result_with_findings(self, tmp_path: Path) -> None:
        runner = StubCheckRunner(security_critical=1, security_high=1)
        result = runner.run_security(tmp_path / "agent.py")
        assert result.is_safe is False
        assert result.total_findings == 2
