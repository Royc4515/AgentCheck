from __future__ import annotations

"""Validation stubs — kept for backwards-compatibility with older code.

The empirical agent-generation pipeline (LLMAgentGenerator, FairnessGuard,
ValidationPipeline) has been removed.  Check #4 operates in KB-only mode:
it surfaces real-world alternative frameworks from the YAML knowledge base
together with their documented pros/cons, without generating or executing
alternative agent code.

For future empirical comparison work, wire up CheckRunner implementations
in check_runner.py instead.
"""

from pathlib import Path


class BatteryRunner:
    """Deprecated stub — superseded by CheckRunner.

    Kept so any external code that references this class does not break on import.
    New code should use CheckRunner / StubCheckRunner from check_runner.py.
    """

    def run(self, agent_path: Path, tasks_path: Path) -> tuple[float, float]:
        raise NotImplementedError(
            "BatteryRunner is superseded by CheckRunner. "
            "Use StubCheckRunner or RealCheckRunner instead."
        )
