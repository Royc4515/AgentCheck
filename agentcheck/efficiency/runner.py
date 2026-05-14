"""Part 2 — Efficiency runner.

Loads the agent at ``agent_path``, executes it in the sandbox, analyses
token usage / cost / tool calls, and writes ``wastefulness_result.json``
under the supplied ``results_dir``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from agentcheck.alternatives.models import WastefulnessResult
from agentcheck.shared import ensure_results_dir, write_json

from .analyzer import (
    analyze_llm_baseline,
    analyze_tool_calls,
    estimate_cost,
)
from .downgrade_tester import get_cheaper_model
from .reporter import calculate_waste_score, print_terminal_report
from .sandbox_runner import run_sandbox_from_path

_PRICING_PATH = Path(__file__).parent / "pricing.yaml"


def _load_pricing() -> dict:
    with open(_PRICING_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_efficiency(
    agent_path: Path,
    results_dir: Path,
    task_prompt: str = "Summarise this task in one sentence.",
    model: str = "gpt-4o-mini",
) -> WastefulnessResult:
    """Run the Part 2 wastefulness check against the agent at ``agent_path``."""
    agent_path = Path(agent_path).resolve()
    results_dir = ensure_results_dir(Path(results_dir))

    log = run_sandbox_from_path(
        agent_path=agent_path,
        task_input=task_prompt,
        model_name=model,
        results_dir=results_dir,
    )
    pricing = _load_pricing()

    actual_cost, actual_tokens = estimate_cost(log, pricing)
    tool_penalty_pts, redundant_tools = analyze_tool_calls(log)
    baseline_tokens, is_bloated = analyze_llm_baseline(task_prompt, actual_tokens)

    mini = pricing["models"].get("gpt-4o-mini", {})
    baseline_cost = (
        ((baseline_tokens / 1_000_000) * mini.get("input_per_1m", 0))
        + ((20 / 1_000_000) * mini.get("output_per_1m", 0))
    )

    original_model = log["agent_metadata"]["model_used"]
    cheaper_model = get_cheaper_model(original_model)
    overspec_penalty = 0.0
    if cheaper_model and original_model in pricing["models"] and cheaper_model in pricing["models"]:
        orig_rate = pricing["models"][original_model]["input_per_1m"]
        cheap_rate = pricing["models"][cheaper_model]["input_per_1m"]
        overspec_penalty = max(0.0, (actual_tokens / 1_000_000) * (orig_rate - cheap_rate))

    metrics = {
        "actual_cost": actual_cost,
        "baseline_cost": baseline_cost,
        "actual_tokens": actual_tokens,
        "baseline_tokens": baseline_tokens,
        "actual_latency": log["execution_log"]["total_latency_seconds"],
        "baseline_latency": 1.5,
        "overspec_penalty": overspec_penalty,
        "original_model": original_model,
        "cheaper_model": cheaper_model,
        "bloat_penalty": actual_cost * 0.15 if is_bloated else 0.0,
        "tool_penalty": (tool_penalty_pts / 100) * 0.01,
        "redundant_tools": redundant_tools,
    }

    print_terminal_report(metrics)
    waste_score = float(calculate_waste_score(baseline_cost, actual_cost))
    token_bloat_pct = 0.0
    if baseline_tokens > 0 and actual_tokens > baseline_tokens:
        token_bloat_pct = round(((actual_tokens - baseline_tokens) / baseline_tokens) * 100, 2)

    result = WastefulnessResult(
        waste_score=waste_score,
        cost_per_task_usd=round(actual_cost, 6),
        baseline_cost_usd=round(baseline_cost, 6),
        token_bloat_pct=token_bloat_pct,
        model_over_spec=bool(cheaper_model and overspec_penalty > 0),
        suggested_model=cheaper_model if overspec_penalty > 0 else None,
        redundant_tool_calls=len(redundant_tools),
        retry_storms_detected=0,
        has_parallelizable_calls=False,
    )

    out_path = results_dir / "wastefulness_result.json"
    write_json(out_path, result)
    print(f"[efficiency] Waste score {waste_score:.0f}/100 — wrote {out_path.name}")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("agent_path", type=Path)
    parser.add_argument("--results-dir", type=Path, default=Path(".agentcheck"))
    parser.add_argument("--prompt", type=str, default="Summarise this task in one sentence.")
    args = parser.parse_args()
    run_efficiency(args.agent_path, args.results_dir, task_prompt=args.prompt)
