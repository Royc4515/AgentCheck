from __future__ import annotations

"""Empirical Validation Pipeline — skeleton for --validate-alternative.

This module handles the "expensive mode" described in SDD v0.4 §4.1:
  1. Auto-Generate: ask an LLM to write a minimal equivalent agent in the
     target framework.
  2. Re-Run Battery: execute the task battery from Check #1 against the
     generated agent.
  3. Compare: measure whether the alternative actually dominates.

The pipeline is intentionally separated from the MatchingEngine so that
KB-only analysis (cheap, default) never pays the generation + re-run cost.
"""

import abc
import textwrap
from pathlib import Path
from typing import Optional

from .models import (
    AgentProfile,
    AlternativeCandidate,
    ValidationResult,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Fair-comparison contract
# ---------------------------------------------------------------------------

class FairnessViolation(Exception):
    """Raised when the generated alternative cannot be a fair comparison.

    A fair comparison requires:
    - Same task battery (identical inputs, identical judge)
    - Same tool surface (mock layer applied equally)
    - Generated agent must be standalone (no hidden imports that pre-solve tasks)
    """


class FairnessGuard:
    """Static checks run against the generated agent *before* the battery.

    These are lightweight heuristics, not a guarantee — the auto-generate step
    is inherently noisy. The guard reduces the chance of reporting a false win.
    """

    _FORBIDDEN_IMPORTS = frozenset({
        "pickle",
        "shelve",
        "dill",
    })

    _TASK_SOLUTION_LEAK_PATTERNS = [
        "expected_output",
        "ground_truth",
        "HARDCODED_ANSWER",
    ]

    def validate(self, source_code: str, candidate: AlternativeCandidate) -> None:
        self._check_forbidden_imports(source_code)
        self._check_solution_leakage(source_code)

    def _check_forbidden_imports(self, source_code: str) -> None:
        for mod in self._FORBIDDEN_IMPORTS:
            if f"import {mod}" in source_code or f"from {mod}" in source_code:
                raise FairnessViolation(
                    f"Generated agent imports '{mod}' — potential unsafe deserialization. "
                    "Refusing to run battery."
                )

    def _check_solution_leakage(self, source_code: str) -> None:
        for pattern in self._TASK_SOLUTION_LEAK_PATTERNS:
            if pattern in source_code:
                raise FairnessViolation(
                    f"Generated agent source contains '{pattern}' — "
                    "looks like the task answer was baked in. "
                    "This would not be a fair comparison."
                )


# ---------------------------------------------------------------------------
# Agent generator abstraction
# ---------------------------------------------------------------------------

class AgentGeneratorBase(abc.ABC):
    """Generates a minimal equivalent agent for the target framework.

    Concrete implementations swap in different LLM backends. The default
    implementation in this skeleton raises NotImplementedError so the module
    can be imported and tested without live API credentials.
    """

    @abc.abstractmethod
    def generate(
        self,
        profile: AgentProfile,
        candidate: AlternativeCandidate,
        output_dir: Path,
    ) -> Path:
        """Write a Python file implementing the agent and return its path."""
        ...


class LLMAgentGenerator(AgentGeneratorBase):
    """Uses an Anthropic / OpenAI model to write the alternative agent.

    The prompt is deliberately minimal: give the LLM the original agent's
    task description and target framework, ask for the smallest possible
    implementation.  We do NOT pass the original source code — that would
    let the LLM copy logic verbatim and inflate the reliability score.
    """

    _GENERATION_PROMPT = textwrap.dedent("""\
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
        - Add a `if __name__ == "__main__"` block that calls run() with a sample input.

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
        # Deferred import — keeps the module importable without anthropic installed
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package required for --validate-alternative. "
                "Run: pip install anthropic"
            ) from exc

        task_desc = _infer_task_description(profile)
        prompt = self._GENERATION_PROMPT.format(
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
    """Best-effort task description from profile; falls back to a generic prompt."""
    if profile.detected_patterns:
        pattern = profile.detected_patterns[0].value.replace("_", " ")
        return f"Perform {pattern} on the provided text."
    return "Process the provided input and return a result."


# ---------------------------------------------------------------------------
# Battery runner stub
# ---------------------------------------------------------------------------

class BatteryRunner:
    """Re-runs the Check #1 task battery against the generated agent.

    This is a stub — full implementation depends on the v0.1 Sandbox Runner
    (milestone M2).  The interface is defined here so ValidationPipeline can
    be fully tested with a mock runner.
    """

    def run(
        self,
        agent_path: Path,
        tasks_path: Path,
    ) -> tuple[float, float]:
        """Return (task_completion_rate, cost_per_task_usd).

        Raises NotImplementedError until v0.1 Sandbox Runner is wired up.
        """
        raise NotImplementedError(
            "BatteryRunner requires the v0.1 Sandbox Runner (milestone M2). "
            "Pass a mock BatteryRunner to ValidationPipeline for testing."
        )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class ValidationPipeline:
    """Orchestrates Auto-Generate → Fairness Check → Re-Run Battery → Compare.

    Parameters
    ----------
    generator:
        Produces the alternative agent source.  Defaults to LLMAgentGenerator.
    runner:
        Executes the task battery.  Defaults to BatteryRunner (stub).
    output_dir:
        Where generated agent files are written.  Defaults to .agentcheck/alternatives/.
    """

    def __init__(
        self,
        generator: Optional[AgentGeneratorBase] = None,
        runner: Optional[BatteryRunner] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._generator = generator or LLMAgentGenerator()
        self._runner = runner or BatteryRunner()
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
            # Step 1: generate
            agent_path = self._generator.generate(profile, candidate, self._output_dir)
            result.generated_agent_path = str(agent_path)

            # Step 2: fairness guard
            self._fairness.validate(agent_path.read_text(encoding="utf-8"), candidate)

            # Step 3: re-run battery
            completion_rate, cost = self._runner.run(agent_path, tasks_path)
            result.task_completion_rate = completion_rate
            result.cost_per_task_usd = cost

            # Step 4: compare against original
            result.confirmed_dominates = self._compare(profile, result, candidate)
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

    @staticmethod
    def _compare(
        profile: AgentProfile,
        result: ValidationResult,
        candidate: AlternativeCandidate,
    ) -> bool:
        """Empirical dominance: alternative must beat on ≥1 axis, regress on none."""
        wins = 0

        if (
            profile.task_completion_rate is not None
            and result.task_completion_rate is not None
        ):
            rel_delta = result.task_completion_rate - profile.task_completion_rate
            if rel_delta < -0.15:
                return False  # regression guard
            if rel_delta >= 0.10:
                wins += 1

        if (
            profile.cost_per_task_usd is not None
            and result.cost_per_task_usd is not None
            and profile.cost_per_task_usd > 0
        ):
            cost_delta = (profile.cost_per_task_usd - result.cost_per_task_usd) / profile.cost_per_task_usd
            if cost_delta < -0.15:
                return False  # alternative is significantly more expensive
            if cost_delta >= 0.30:
                wins += 1

        return wins > 0
