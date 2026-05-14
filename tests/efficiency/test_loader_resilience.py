"""Regression: a target agent with missing imports must not crash AgentCheck."""

from pathlib import Path

from agentcheck.efficiency.sandbox_runner import run_sandbox_from_path


def test_missing_import_does_not_raise(tmp_path: Path) -> None:
    bad = tmp_path / "broken_agent.py"
    bad.write_text("from definitely_not_a_real_module import foo\n", encoding="utf-8")

    results_dir = tmp_path / ".agentcheck"
    log = run_sandbox_from_path(
        bad.resolve(), "hello", results_dir=results_dir
    )

    assert log["execution_log"]["status"] == "error"
    assert "definitely_not_a_real_module" in log["execution_log"]["error"]
    assert (results_dir / "execution_log.json").exists()


def test_no_public_function_does_not_raise(tmp_path: Path) -> None:
    bad = tmp_path / "empty_agent.py"
    bad.write_text("_x = 1\n", encoding="utf-8")

    log = run_sandbox_from_path(bad.resolve(), "hello")
    assert log["execution_log"]["status"] == "error"
