"""Sandboxed agent execution that captures token usage and latency.

The agent itself is loaded from a caller-supplied path (``agent_path``)
rather than imported from a fixed module. The execution log is written
under ``results_dir/execution_log.json`` — never to the repo root.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

from .utils import count_tokens


def _load_callable_from_path(
    agent_path: Path, function_name: Optional[str] = None
) -> Callable[..., Any]:
    spec = importlib.util.spec_from_file_location(
        f"agentcheck_eff_{agent_path.stem}", str(agent_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {agent_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    if function_name:
        return getattr(module, function_name)

    candidates: list[tuple[str, Callable[..., Any]]] = [
        (name, obj)
        for name, obj in inspect.getmembers(module, inspect.isfunction)
        if obj.__module__ == spec.name and not name.startswith("_")
    ]
    if not candidates:
        raise AttributeError(f"No public function found in {agent_path}")
    preferred = [c for c in candidates if "agent" in c[0].lower()]
    return (preferred[0] if preferred else candidates[0])[1]


def _normalise_response(raw: Any, task_input: str) -> dict[str, Any]:
    """Coerce arbitrary agent return values into the metrics dict we need."""
    if isinstance(raw, dict) and "system_tokens" in raw:
        return raw
    text = raw if isinstance(raw, str) else json.dumps(raw, default=str)
    return {
        "status": "success",
        "system_tokens": 100,
        "user_tokens": count_tokens(task_input),
        "completion_tokens": count_tokens(text),
        "tools_called": [],
    }


def run_sandbox(
    agent_func: Callable[..., Any],
    task_input: str,
    model_name: str = "gpt-4o-mini",
    results_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Execute ``agent_func`` once, capture metrics, write log to results_dir."""
    start_time = time.time()
    try:
        raw = agent_func(task_input)
        response = _normalise_response(raw, task_input)
        status = response.get("status", "success")
    except Exception as e:  # noqa: BLE001
        response = {}
        status = "error"
        print(f"[Runner] Agent execution failed: {e}")

    latency = round(time.time() - start_time, 2)

    log = {
        "task_id": "test_001",
        "task_input_size_chars": len(task_input),
        "agent_metadata": {"model_used": model_name},
        "execution_log": {
            "total_latency_seconds": latency,
            "status": status,
            "steps": [
                {
                    "step_id": 1,
                    "type": "llm_call",
                    "latency_seconds": latency,
                    "tokens": {
                        "system": response.get("system_tokens", 0),
                        "user": response.get("user_tokens", 0),
                        "assistant": response.get("completion_tokens", 0),
                        "tool": 0,
                    },
                    "tools_used": response.get("tools_called", []),
                }
            ],
        },
    }

    if results_dir is not None:
        results_dir = Path(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        out = results_dir / "execution_log.json"
        out.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Runner] Execution finished in {latency}s. Log saved to {out}")
    else:
        print(f"[Runner] Execution finished in {latency}s.")

    return log


def _failed_log(agent_path: Path, task_input: str, model_name: str, error: str) -> dict[str, Any]:
    """Return a structured log marking the run as failed without raising."""
    return {
        "task_id": "load_failed",
        "task_input_size_chars": len(task_input),
        "agent_metadata": {"model_used": model_name},
        "execution_log": {
            "total_latency_seconds": 0.0,
            "status": "error",
            "error": error,
            "agent_path": str(agent_path),
            "steps": [
                {
                    "step_id": 1,
                    "type": "load",
                    "latency_seconds": 0.0,
                    "tokens": {"system": 0, "user": 0, "assistant": 0, "tool": 0},
                    "tools_used": [],
                }
            ],
        },
    }


def run_sandbox_from_path(
    agent_path: Path,
    task_input: str,
    model_name: str = "gpt-4o-mini",
    results_dir: Optional[Path] = None,
    function_name: Optional[str] = None,
) -> dict[str, Any]:
    """Convenience wrapper that loads the agent from ``agent_path`` first.

    If the agent cannot be imported (missing deps, syntax error, etc.) the
    failure is recorded in the log instead of crashing the caller — Part 2
    can then report it as a wastefulness "error" without aborting the rest
    of the pipeline.
    """
    agent_path = Path(agent_path).resolve()
    try:
        fn = _load_callable_from_path(agent_path, function_name)
    except (ImportError, ModuleNotFoundError, AttributeError, SyntaxError) as exc:
        print(f"[Runner] Could not load agent at {agent_path}: {exc}")
        log = _failed_log(agent_path, task_input, model_name, str(exc))
        if results_dir is not None:
            results_dir = Path(results_dir)
            results_dir.mkdir(parents=True, exist_ok=True)
            (results_dir / "execution_log.json").write_text(
                json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return log
    return run_sandbox(fn, task_input, model_name=model_name, results_dir=results_dir)
