from __future__ import annotations

"""Empirical Validation Pipeline — --validate-alternative mode.

Flow:
  1. Generate a minimal equivalent agent in the target framework (LLM-written)
  2. FairnessGuard: static checks before the battery runs
  3. Run checks #1, #2, #3 on the generated agent via CheckRunner
     (StubCheckRunner now → RealCheckRunner when checks are implemented)
  4. Compare the empirical AgentProfile against the original
"""

import abc
import textwrap
from pathlib import Path
from typing import Optional

from .check_runner import CheckRunner, StubCheckRunner
from .models import (
    AgentProfile,
    AlternativeCandidate,
    DetectedPattern,
    ReliabilityResult,
    SecurityResult,
    ValidationResult,
    ValidationStatus,
    WastefulnessResult,
)


# ---------------------------------------------------------------------------
# Fairness guard
# ---------------------------------------------------------------------------

class FairnessViolation(Exception):
    """Raised when the generated alternative cannot be a fair comparison."""


class FairnessGuard:
    """Static checks run against the generated agent before the battery."""

    _FORBIDDEN_IMPORTS = frozenset({"pickle", "shelve", "dill"})
    _SOLUTION_LEAK_PATTERNS = ["expected_output", "ground_truth", "HARDCODED_ANSWER"]

    def validate(self, source_code: str, candidate: AlternativeCandidate) -> None:
        self._check_forbidden_imports(source_code)
        self._check_solution_leakage(source_code)

    def _check_forbidden_imports(self, source_code: str) -> None:
        for mod in self._FORBIDDEN_IMPORTS:
            if f"import {mod}" in source_code or f"from {mod}" in source_code:
                raise FairnessViolation(
                    f"Generated agent imports '{mod}' — unsafe deserialization risk."
                )

    def _check_solution_leakage(self, source_code: str) -> None:
        for pattern in self._SOLUTION_LEAK_PATTERNS:
            if pattern in source_code:
                raise FairnessViolation(
                    f"Generated agent contains '{pattern}' — answer appears baked in."
                )


# ---------------------------------------------------------------------------
# Agent generator
# ---------------------------------------------------------------------------

class AgentGeneratorBase(abc.ABC):
    @abc.abstractmethod
    def generate(
        self,
        profile: AgentProfile,
        candidate: AlternativeCandidate,
        output_dir: Path,
    ) -> Path: ...


class LLMAgentGenerator(AgentGeneratorBase):
    """Uses an Anthropic model to write the alternative agent."""

    _PROMPT = textwrap.dedent("""\
        You are an expert Python developer.

        Write a minimal, self-contained Python agent that:
        1. Uses the {framework} framework (no other agent frameworks).
        2. Accepts a single string input called `user_input`.
        3. Exposes a function `run(user_input: str) -> str`.
        4. Solves this task: {task_description}

        Rules:
        - Keep it under 80 lines.
        - No hardcoded answers.
        - No imports beyond {framework} and the Python stdlib.

        Return ONLY the Python source code, no explanation.
    """)

    def __init__(self, model_id: str = "claude-haiku-4-5-20251001") -> None:
        self._model_id = model_id

    def generate(
        self,
        profile: AgentProfile,
        candidate: AlternativeCandidate,
        output_dir: Path,
    ) -> Path:
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package required for --validate-alternative. "
                "Run: pip install anthropic"
            ) from exc

        task_desc = _infer_task_description(profile)
        prompt = self._PROMPT.format(
            framework=candidate.name,
            task_description=task_desc,
        )
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self._model_id,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        source_code: str = response.content[0].text.strip()

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"alt_{candidate.id}_agent.py"
        out_path.write_text(source_code, encoding="utf-8")
        return out_path


def _infer_task_description(profile: AgentProfile) -> str:
    if profile.detected_patterns:
        pattern = profile.detected_patterns[0].value.replace("_", " ")
        return f"Perform {pattern} on the provided text."
    return "Process the provided input and return a result."


# ---------------------------------------------------------------------------
# Legacy BatteryRunner stub (kept for backwards-compat with old tests)
# ---------------------------------------------------------------------------

class BatteryRunner:
    """Deprecated stub — superseded by CheckRunner.

    Kept only so existing tests that mock this class don't break.
    New code should use CheckRunner / StubCheckRunner.
    """

    def run(self, agent_path: Path, tasks_path: Path) -> tuple[float, float]:
        raise NotImplementedError(
            "BatteryRunner is superseded by CheckRunner. "
            "Use StubCheckRunner or RealCheckRunner instead."
        )


# ---------------------------------------------------------------------------
# Validation pipeline
# ---------------------------------------------------------------------------

class ValidationPipeline:
    """Orchestrates: Generate → FairnessGuard → Run #1/#2/#3 → Compare.

    Parameters
    ----------
    generator:
        Writes the alternative agent source.  Defaults to LLMAgentGenerator.
    runner:
        Runs checks #1, #2, #3 on the generated agent.
        Defaults to StubCheckRunner — swap for RealCheckRunner when ready.
    output_dir:
        Where generated agent files are written.
    """

    def __init__(
        self,
        generator: Optional[AgentGeneratorBase] = None,
        runner: Optional[CheckRunner] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._generator = generator or LLMAgentGenerator()
        self._runner = runner or StubCheckRunner()
        self._output_dir = output_dir or Path(".agentcheck") / "alternatives"
        self._fairness = FairnessGuard()

    def validate(
        self,
        profile: AgentProfile,
        candidate: AlternativeCandidate,
        tasks_path: Path,
    ) -> ValidationResult:
        result = ValidationResult(
            candidate_id=candidate.id,
            status=ValidationStatus.RUNNING,
        )

        try:
            # Step 1: generate alternative agent
            agent_path = self._generator.generate(profile, candidate, self._output_dir)
            result.generated_agent_path = str(agent_path)

            # Step 2: fairness guard
            self._fairness.validate(agent_path.read_text(encoding="utf-8"), candidate)

            # Step 3: run checks #1, #2, #3 on the alternative
            reliability = self._runner.run_reliability(agent_path, tasks_path)
            wastefulness = self._runner.run_wastefulness(agent_path, tasks_path)
            security = self._runner.run_security(agent_path)

            # Populate convenience fields for backwards compat
            result.task_completion_rate = reliability.task_completion_rate
            result.cost_per_task_usd = wastefulness.cost_per_task_usd

            # Step 4: compare empirical profile against original
            alt_profile = _build_alt_profile(candidate, reliability, wastefulness, security)
            result.confirmed_dominates = _compare(profile, alt_profile)
            result.status = (
                ValidationStatus.PASSED
                if result.confirmed_dominates
                else ValidationStatus.FAILED
            )

        except FairnessViolation as exc:
            result.status = ValidationStatus.ERROR
            result.error_message = f"[FairnessViolation] {exc}"
        except NotImplementedError as exc:
            result.status = ValidationStatus.ERROR
            result.error_message = f"[NotImplemented] {exc}"
        except Exception as exc:  # noqa: BLE001
            result.status = ValidationStatus.ERROR
            result.error_message = f"[Unexpected] {type(exc).__name__}: {exc}"

        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_alt_profile(
    candidate: AlternativeCandidate,
    reliability: ReliabilityResult,
    wastefulness: WastefulnessResult,
    security: SecurityResult,
) -> AgentProfile:
    return AgentProfile(
        framework=candidate.id,
        framework_confidence=1.0,
        reliability=reliability,
        wastefulness=wastefulness,
        security=security,
    )


def _compare(original: AgentProfile, alt: AgentProfile) -> bool:
    """Empirical dominance: alt must win ≥1 axis, regress on none."""
    wins = 0

    if original.task_completion_rate is not None and alt.task_completion_rate is not None:
        delta = alt.task_completion_rate - original.task_completion_rate
        if delta < -0.15:
            return False
        if delta >= 0.10:
            wins += 1

    if (
        original.cost_per_task_usd is not None
        and alt.cost_per_task_usd is not None
        and original.cost_per_task_usd > 0
    ):
        delta = (original.cost_per_task_usd - alt.cost_per_task_usd) / original.cost_per_task_usd
        if delta < -0.15:
            return False
        if delta >= 0.30:
            wins += 1

    if original.security_finding_count is not None and alt.security_finding_count is not None:
        if alt.security_finding_count > original.security_finding_count:
            return False
        if alt.security_finding_count < original.security_finding_count:
            wins += 1

    return wins > 0
