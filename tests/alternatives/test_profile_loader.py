"""Tests for AgentProfileLoader — reads check #1/#2/#3 JSONs into AgentProfile."""

import json
import pytest
from pathlib import Path

from agentcheck.alternatives import (
    AgentProfile,
    AgentProfileLoader,
    CheckResultNotFound,
    DetectedPattern,
)


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture()
def results_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def reliability_json() -> dict:
    return {
        "task_completion_rate": 0.80,
        "tasks_passed": 8,
        "tasks_total": 10,
        "framework": "langchain",
        "framework_confidence": 0.94,
        "model_id": "claude-sonnet-4-6",
        "detected_patterns": ["react_loop"],
        "loc": 180,
        "cyclomatic_complexity": 24,
    }


@pytest.fixture()
def wastefulness_json() -> dict:
    return {
        "waste_score": 62.0,
        "cost_per_task_usd": 0.045,
        "baseline_cost_usd": 0.017,
        "token_bloat_pct": 34.0,
        "model_over_spec": True,
        "suggested_model": "claude-haiku-4-5-20251001",
        "redundant_tool_calls": 2,
        "retry_storms_detected": 0,
        "has_parallelizable_calls": True,
    }


@pytest.fixture()
def security_json() -> dict:
    return {
        "is_safe": False,
        "critical_count": 1,
        "high_count": 2,
        "medium_count": 1,
        "low_count": 3,
        "finding_ids": ["SEC-001", "SEC-002", "SEC-003", "SEC-004", "SEC-005", "SEC-006", "SEC-007"],
        "hardcoded_secrets": True,
        "prompt_injection_vulnerable": True,
        "unsafe_deserialization": False,
    }


class TestProfileLoader:
    def test_loads_all_three_files(
        self,
        results_dir: Path,
        reliability_json: dict,
        wastefulness_json: dict,
        security_json: dict,
    ) -> None:
        _write(results_dir / "reliability_result.json", reliability_json)
        _write(results_dir / "wastefulness_result.json", wastefulness_json)
        _write(results_dir / "security_result.json", security_json)

        profile = AgentProfileLoader(results_dir=results_dir).load()

        assert profile.framework == "langchain"
        assert profile.task_completion_rate == pytest.approx(0.80)
        assert profile.cost_per_task_usd == pytest.approx(0.045)
        assert profile.security_finding_count == 7  # 1+2+1+3

    def test_convenience_properties_map_correctly(
        self,
        results_dir: Path,
        reliability_json: dict,
        wastefulness_json: dict,
        security_json: dict,
    ) -> None:
        _write(results_dir / "reliability_result.json", reliability_json)
        _write(results_dir / "wastefulness_result.json", wastefulness_json)
        _write(results_dir / "security_result.json", security_json)

        profile = AgentProfileLoader(results_dir=results_dir).load()

        assert profile.loc == 180
        assert profile.waste_score == pytest.approx(62.0)
        assert profile.detected_patterns == [DetectedPattern.REACT_LOOP]

    def test_partial_load_missing_security(
        self,
        results_dir: Path,
        reliability_json: dict,
        wastefulness_json: dict,
    ) -> None:
        """Missing security JSON should not raise in non-strict mode."""
        _write(results_dir / "reliability_result.json", reliability_json)
        _write(results_dir / "wastefulness_result.json", wastefulness_json)

        profile = AgentProfileLoader(results_dir=results_dir, strict=False).load()

        assert profile.security is None
        assert profile.security_finding_count is None
        # Other checks still loaded
        assert profile.task_completion_rate == pytest.approx(0.80)

    def test_partial_load_only_reliability(
        self,
        results_dir: Path,
        reliability_json: dict,
    ) -> None:
        _write(results_dir / "reliability_result.json", reliability_json)

        profile = AgentProfileLoader(results_dir=results_dir).load()

        assert profile.framework == "langchain"
        assert profile.wastefulness is None
        assert profile.cost_per_task_usd is None

    def test_strict_mode_raises_on_missing_file(self, results_dir: Path) -> None:
        loader = AgentProfileLoader(results_dir=results_dir, strict=True)

        with pytest.raises(CheckResultNotFound):
            loader.load()

    def test_empty_results_dir_returns_empty_profile(self, results_dir: Path) -> None:
        profile = AgentProfileLoader(results_dir=results_dir, strict=False).load()

        assert isinstance(profile, AgentProfile)
        assert profile.framework is None
        assert profile.task_completion_rate is None

    def test_unknown_pattern_skipped_gracefully(
        self,
        results_dir: Path,
        reliability_json: dict,
    ) -> None:
        reliability_json["detected_patterns"] = ["react_loop", "not_a_real_pattern"]
        _write(results_dir / "reliability_result.json", reliability_json)

        profile = AgentProfileLoader(results_dir=results_dir).load()

        assert DetectedPattern.REACT_LOOP in profile.detected_patterns
        assert len(profile.detected_patterns) == 1  # unknown one was dropped
