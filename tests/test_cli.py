"""CLI argument-handling regression tests."""

from pathlib import Path
from unittest.mock import patch

from agentcheck.cli import build_parser, main


def test_no_agent_path_defaults_to_alternatives_only(tmp_path: Path) -> None:
    with patch("agentcheck.cli.run_pipeline") as run:
        main(["run", "--results-dir", str(tmp_path)])
        kwargs = run.call_args.kwargs
        assert kwargs["agent_path"] is None
        assert kwargs["only"] == {"alternatives"}
        assert kwargs["skip"] == set()


def test_skip_alternatives_is_honored_without_agent_path(tmp_path: Path) -> None:
    """Regression: `--skip alternatives` must NOT be overridden by the
    no-agent-path default that forces `--only alternatives`."""
    with patch("agentcheck.cli.run_pipeline") as run:
        main(["run", "--skip", "alternatives", "--results-dir", str(tmp_path)])
        kwargs = run.call_args.kwargs
        assert kwargs["only"] == set()  # no auto-default
        assert kwargs["skip"] == {"alternatives"}


def test_explicit_only_is_preserved(tmp_path: Path) -> None:
    with patch("agentcheck.cli.run_pipeline") as run:
        main(["run", "--only", "alternatives", "--results-dir", str(tmp_path)])
        kwargs = run.call_args.kwargs
        assert kwargs["only"] == {"alternatives"}


def test_quality_runner_does_not_import_alternatives_package() -> None:
    """Regression: importing run_quality must not load the alternatives stack."""
    import importlib
    import sys

    for mod in list(sys.modules):
        if mod.startswith("agentcheck"):
            del sys.modules[mod]

    importlib.import_module("agentcheck.quality.runner")
    assert "agentcheck.alternatives" not in sys.modules
    assert "agentcheck.alternatives.alternatives_engine" not in sys.modules
