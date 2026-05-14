"""Quality / Reliability check (Part 1).

Public entry point::

    from agentcheck.quality import run_quality
    result = run_quality(agent_path=Path("./my_agent.py"), results_dir=Path(".agentcheck"))
"""

from .runner import run_quality

__all__ = ["run_quality"]
