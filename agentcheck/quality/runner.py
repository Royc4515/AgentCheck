"""Part 1 — Quality runner.

Receives the resolved agent_path, reads source for framework/LOC detection,
dynamically loads a callable from the file, runs an LLM-generated test
battery against it, and writes ``reliability_result.json``.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from agentcheck.shared.models import ReliabilityResult
from agentcheck.shared import OpenRouterClient, ensure_results_dir, write_json
from agentcheck.shared.openrouter_client import OpenRouterError

from .evaluator import QualityEvaluator
from .generator import DynamicTestGenerator

_FRAMEWORK_PATTERNS: dict[str, list[str]] = {
    "langchain": [r"\blangchain\b", r"from langchain"],
    "llamaindex": [r"\bllama_index\b", r"from llama_index"],
    "autogen": [r"\bautogen\b", r"from autogen"],
    "pydanticai": [r"\bpydantic_ai\b", r"from pydantic_ai"],
    "openai_sdk": [r"\bfrom openai\b", r"\bimport openai\b"],
    "anthropic_sdk": [r"\bfrom anthropic\b", r"\bimport anthropic\b"],
}


def _detect_framework(source: str) -> tuple[Optional[str], float]:
    for name, patterns in _FRAMEWORK_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, source):
                return name, 0.85
    return None, 0.0


def _count_loc(source: str) -> int:
    return sum(
        1
        for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _load_agent_callable(agent_path: Path) -> tuple[Callable[..., Any], str]:
    """Dynamically import ``agent_path`` and return the most likely agent function."""
    spec = importlib.util.spec_from_file_location(
        f"agentcheck_target_{agent_path.stem}", str(agent_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {agent_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    candidates: list[tuple[str, Callable[..., Any]]] = []
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != spec.name:
            continue
        if name.startswith("_"):
            continue
        candidates.append((name, obj))

    if not candidates:
        raise AttributeError(f"No public function found in {agent_path}")

    preferred = [c for c in candidates if "agent" in c[0].lower()]
    chosen = preferred[0] if preferred else candidates[0]
    return chosen[1], chosen[0]


def _invoke_agent(fn: Callable[..., Any], prompt: str) -> str:
    sig = inspect.signature(fn)
    params = [
        p for p in sig.parameters.values()
        if p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)
    ]
    try:
        result = fn(prompt) if params else fn()
    except TypeError:
        result = fn(prompt)
    if isinstance(result, dict):
        for k in ("output", "content", "text", "response", "answer"):
            if k in result and isinstance(result[k], str):
                return result[k]
        return str(result)
    return str(result)


def _infer_purpose(agent_path: Path, source: str, function_name: str) -> str:
    docstring_match = re.search(r'"""(.+?)"""', source, re.DOTALL)
    if docstring_match:
        return docstring_match.group(1).strip().splitlines()[0]
    return f"AI agent exposed as `{function_name}` in {agent_path.name}"


class _LLMClientShim:
    """Adapter so existing generator/evaluator code can call ``generate(prompt)``."""

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    def generate(self, prompt: str) -> str:
        try:
            return self._client.chat(
                [
                    {
                        "role": "system",
                        "content": "You are a precise JSON-generating system. Return strictly valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                json_mode=True,
            )
        except OpenRouterError as exc:
            return f'{{"error": "{exc}"}}'


def run_quality(
    agent_path: Path,
    results_dir: Path,
    task: Optional[str] = None,
    agent_description: Optional[str] = None,
) -> ReliabilityResult:
    """Execute Part 1 against the agent at ``agent_path`` and persist results."""
    agent_path = Path(agent_path).resolve()
    results_dir = ensure_results_dir(Path(results_dir))

    source = agent_path.read_text(encoding="utf-8", errors="replace")
    framework, confidence = _detect_framework(source)
    loc = _count_loc(source)

    tasks_passed = 0
    tasks_total = 1
    detected_patterns: list[str] = []

    try:
        agent_fn, fn_name = _load_agent_callable(agent_path)
        if task and agent_description:
            purpose = f"{agent_description}. Task: {task}"
        elif task:
            purpose = task
        elif agent_description:
            purpose = agent_description
        else:
            purpose = _infer_purpose(agent_path, source, fn_name)
        client = OpenRouterClient()
        shim = _LLMClientShim(client)
        generator = DynamicTestGenerator(shim)
        evaluator = QualityEvaluator(shim)

        suite = generator.generate_suite(purpose) if client.has_key else {}
        tests = suite.get("tests", []) or []
        metrics = suite.get("custom_metrics", []) or []

        if not tests:
            tests = [{"name": "smoke", "prompt": "Hello, please respond.", "type": "happy_path"}]

        outputs: dict[str, str] = {}
        prompts: dict[str, str] = {}
        for t in tests:
            name = t.get("name", "test")
            test_prompt = t.get("prompt", "")
            prompts[name] = test_prompt
            try:
                outputs[name] = _invoke_agent(agent_fn, test_prompt)
            except Exception as exc:  # noqa: BLE001
                outputs[name] = f"[ERROR] {exc}"

        if metrics and client.has_key:
            judged = evaluator.evaluate_all(outputs, metrics, test_prompts=prompts)
            tasks_total = max(1, len(outputs))
            tasks_passed = sum(
                1
                for _, data in judged.get("breakdown", {}).items()
                if data.get("score", 0) >= 60
            )
        else:
            tasks_total = max(1, len(outputs))
            tasks_passed = sum(
                1
                for v in outputs.values()
                if not v.startswith("[ERROR]") and len(v.strip()) >= 50
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[quality] Skipping deep evaluation: {exc}")
        tasks_total = 1
        tasks_passed = 0

    completion_rate = tasks_passed / tasks_total if tasks_total else 0.0
    result = ReliabilityResult(
        task_completion_rate=round(completion_rate, 4),
        tasks_passed=tasks_passed,
        tasks_total=tasks_total,
        framework=framework,
        framework_confidence=confidence,
        detected_patterns=detected_patterns,
        loc=loc,
    )

    out_path = results_dir / "reliability_result.json"
    write_json(out_path, result)
    print(
        f"[quality] {tasks_passed}/{tasks_total} tests passed "
        f"({completion_rate:.0%}) — wrote {out_path.name}"
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("agent_path", type=Path)
    parser.add_argument("--results-dir", type=Path, default=Path(".agentcheck"))
    args = parser.parse_args()
    run_quality(args.agent_path, args.results_dir)
