from __future__ import annotations

"""CheckRunner — interface between check #4 (Alternatives) and checks #1/#2/#3.

This module defines the contract that checks #1, #2, #3 must satisfy when
called by the empirical validation pipeline.  For now, StubCheckRunner
returns realistic fake data so the rest of the pipeline can be developed
and tested end-to-end.

When the real checks are ready, replace StubCheckRunner with RealCheckRunner
(see the clearly marked swap point at the bottom of this file).
"""

import abc
import random
from pathlib import Path

from .models import ReliabilityResult, SecurityResult, WastefulnessResult


class CheckRunner(abc.ABC):
    """Abstract interface for running checks #1, #2, #3 on any agent path.

    Each method receives the agent source file and the task battery path,
    and returns the same JSON-compatible model that the real check produces.
    """

    @abc.abstractmethod
    def run_reliability(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> ReliabilityResult:
        """Run check #1 on the agent and return a ReliabilityResult."""
        ...

    @abc.abstractmethod
    def run_wastefulness(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> WastefulnessResult:
        """Run check #2 on the agent and return a WastefulnessResult."""
        ...

    @abc.abstractmethod
    def run_security(
        self,
        agent_path: Path,
    ) -> SecurityResult:
        """Run check #3 on the agent and return a SecurityResult."""
        ...


class StubCheckRunner(CheckRunner):
    """Returns plausible fake results for development and testing.

    The stub simulates a 'typical well-behaved agent' — moderate reliability,
    low waste, clean security.  Pass explicit values via the constructor to
    control the output in tests.

    ─────────────────────────────────────────────────────────────────────
    SWAP POINT: when checks #1, #2, #3 are implemented, replace this class
    with RealCheckRunner (stub at the bottom of this file).
    ─────────────────────────────────────────────────────────────────────
    """

    def __init__(
        self,
        task_completion_rate: float = 0.80,
        cost_per_task_usd: float = 0.025,
        waste_score: float = 35.0,
        security_critical: int = 0,
        security_high: int = 0,
    ) -> None:
        self._task_completion_rate = task_completion_rate
        self._cost_per_task_usd = cost_per_task_usd
        self._waste_score = waste_score
        self._security_critical = security_critical
        self._security_high = security_high

    def run_reliability(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> ReliabilityResult:
        total = 10
        passed = round(self._task_completion_rate * total)
        return ReliabilityResult(
            task_completion_rate=self._task_completion_rate,
            tasks_passed=passed,
            tasks_total=total,
            framework=_guess_framework(agent_path),
            framework_confidence=0.85,
            detected_patterns=[],
        )

    def run_wastefulness(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> WastefulnessResult:
        baseline = self._cost_per_task_usd * 0.4
        return WastefulnessResult(
            waste_score=self._waste_score,
            cost_per_task_usd=self._cost_per_task_usd,
            baseline_cost_usd=round(baseline, 6),
        )

    def run_security(
        self,
        agent_path: Path,
    ) -> SecurityResult:
        total = self._security_critical + self._security_high
        return SecurityResult(
            is_safe=(total == 0),
            critical_count=self._security_critical,
            high_count=self._security_high,
        )


def _guess_framework(agent_path: Path) -> str:
    """Best-effort framework name from the generated agent filename."""
    name = agent_path.stem.lower()
    for fw in ("pydanticai", "langchain", "autogen", "raw_sdk", "llamaindex"):
        if fw in name:
            return fw
    return "unknown"


# ---------------------------------------------------------------------------
# SWAP POINT — replace StubCheckRunner with this when checks are ready
# ---------------------------------------------------------------------------

class RealCheckRunner(CheckRunner):
    """Calls the real check #1, #2, #3 implementations.

    ── HOW TO WIRE UP ──────────────────────────────────────────────────────
    1. Import the public run functions from each check module:

           from agentcheck.reliability import run as run_reliability_check
           from agentcheck.wastefulness import run as run_wastefulness_check
           from agentcheck.security import run as run_security_check

    2. Replace the NotImplementedError calls below with the real calls.

    3. In AlternativesEngine.__init__, swap:
           runner=StubCheckRunner()
       for:
           runner=RealCheckRunner()
    ────────────────────────────────────────────────────────────────────────
    """

    def run_reliability(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> ReliabilityResult:
        # TODO: from agentcheck.reliability import run as run_check
        # return run_check(agent_path=agent_path, tasks_path=tasks_path)
        raise NotImplementedError("Wire up agentcheck.reliability.run() here.")

    def run_wastefulness(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> WastefulnessResult:
        # TODO: from agentcheck.wastefulness import run as run_check
        # return run_check(agent_path=agent_path, tasks_path=tasks_path)
        raise NotImplementedError("Wire up agentcheck.wastefulness.run() here.")

    def run_security(
        self,
        agent_path: Path,
    ) -> SecurityResult:
        # TODO: from agentcheck.security import run as run_check
        # return run_check(agent_path=agent_path)
        raise NotImplementedError("Wire up agentcheck.security.run() here.")
