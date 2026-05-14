"""Shared pytest fixtures."""

from pathlib import Path

import pytest


_FIXTURE_AGENT_SRC = '''
"""Toy travel-planner agent used by AgentCheck smoke tests."""

def travel_planner_agent(prompt: str) -> str:
    """Return a fixed itinerary so tests are deterministic."""
    return f"Itinerary for {prompt}: 3 attractions, 1 food tip."
'''


@pytest.fixture()
def fixture_agent_path(tmp_path: Path) -> Path:
    """A minimal, dependency-free agent module at a known path."""
    p = tmp_path / "sample_agent.py"
    p.write_text(_FIXTURE_AGENT_SRC, encoding="utf-8")
    return p.resolve()


@pytest.fixture()
def fixture_results_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".agentcheck"
    d.mkdir()
    return d
