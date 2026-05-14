"""Top-level orchestrator: runs Parts 1 → 2 → 3 → 4 in order.

Each part is independent — a failure logs and does not abort later parts.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Optional

from .shared import ensure_results_dir, write_json

_PARTS = ("quality", "efficiency", "security", "alternatives")


def _banner(title: str) -> None:
    bar = "─" * 60
    print(f"\n{bar}\n  {title}\n{bar}")


def run_pipeline(
    agent_path: Optional[Path],
    results_dir: Path,
    skip: Optional[set[str]] = None,
    only: Optional[set[str]] = None,
    task: Optional[str] = None,
    agent_description: Optional[str] = None,
) -> dict:
    """Run the AgentCheck pipeline and return a summary of which parts ran."""
    results_dir = ensure_results_dir(Path(results_dir))
    skip = skip or set()
    only = only or set()

    def should_run(part: str) -> bool:
        if only:
            return part in only
        return part not in skip

    summary: dict[str, str] = {}

    if should_run("quality"):
        _banner("Part 1 — Quality")
        if agent_path is None:
            summary["quality"] = "skipped (no agent path)"
        else:
            try:
                from .quality import run_quality

                run_quality(agent_path, results_dir, task=task, agent_description=agent_description)
                summary["quality"] = "ok"
            except Exception as exc:  # noqa: BLE001
                summary["quality"] = f"error: {exc}"
                traceback.print_exc()

    if should_run("efficiency"):
        _banner("Part 2 — Efficiency")
        if agent_path is None:
            summary["efficiency"] = "skipped (no agent path)"
        else:
            try:
                from .efficiency import run_efficiency

                run_efficiency(agent_path, results_dir)
                summary["efficiency"] = "ok"
            except Exception as exc:  # noqa: BLE001
                summary["efficiency"] = f"error: {exc}"
                traceback.print_exc()

    if should_run("security"):
        _banner("Part 3 — Security")
        if agent_path is None:
            summary["security"] = "skipped (no agent path)"
        else:
            try:
                from .security import run_security

                run_security(agent_path, results_dir)
                summary["security"] = "ok"
            except Exception as exc:  # noqa: BLE001
                summary["security"] = f"error: {exc}"
                traceback.print_exc()

    if should_run("alternatives"):
        _banner("Part 4 — Alternatives")
        try:
            from .alternatives import run as run_alternatives

            report = run_alternatives(results_dir=results_dir)
            write_json(results_dir / "final_report.json", report)
            summary["alternatives"] = "ok"
        except Exception as exc:  # noqa: BLE001
            summary["alternatives"] = f"error: {exc}"
            traceback.print_exc()

    _banner("AgentCheck — Pipeline summary")
    for part, status in summary.items():
        print(f"  {part:<14} {status}")
    print(f"\n  Results written to: {results_dir}")
    return summary
