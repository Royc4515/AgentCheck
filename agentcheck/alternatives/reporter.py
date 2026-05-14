from __future__ import annotations

"""Rich terminal reporter for the Alternatives check.

Three output modes (from SDD v0.4 §5 M21):
  1. terminal  — Rich-styled tables and panels (default)
  2. json      — Machine-readable JSON dump
  3. summary   — Single-line verdict for CI pipelines
"""

import json
from typing import Literal

from .models import AlternativeCandidate, AlternativesReport, RecommendationType

OutputMode = Literal["terminal", "json", "summary"]

# Lazy-import Rich so the module is importable in envs without it installed
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


class AlternativesReporter:
    """Renders an AlternativesReport to the requested output mode."""

    def __init__(self, mode: OutputMode = "terminal") -> None:
        self._mode = mode
        self._console = Console() if _RICH_AVAILABLE else None

    def render(self, report: AlternativesReport) -> str:
        if self._mode == "json":
            return self._render_json(report)
        if self._mode == "summary":
            return self._render_summary(report)
        return self._render_terminal(report)

    # ------------------------------------------------------------------
    # Terminal (Rich)
    # ------------------------------------------------------------------

    def _render_terminal(self, report: AlternativesReport) -> str:
        if not _RICH_AVAILABLE:
            return self._render_summary(report)

        assert self._console is not None
        lines: list[str] = []

        self._console.print()
        self._console.print(
            "[bold cyan]AgentCheck v0.4[/bold cyan] — "
            "[italic]Does a better agent exist? Let's find out.[/italic]"
        )
        self._console.rule(style="cyan")

        # Agent profile summary
        p = report.agent_profile
        profile_lines = []
        if p.framework:
            profile_lines.append(f"Framework : [bold]{p.framework}[/bold] (confidence {p.framework_confidence:.0%})")
        if p.task_completion_rate is not None:
            profile_lines.append(f"Reliability : [bold]{p.task_completion_rate:.0%}[/bold] task completion")
        if p.cost_per_task_usd is not None:
            profile_lines.append(f"Cost/task : [bold]${p.cost_per_task_usd:.4f}[/bold]")
        if p.loc is not None:
            profile_lines.append(f"LOC : [bold]{p.loc}[/bold]")

        if profile_lines:
            self._console.print(Panel("\n".join(profile_lines), title="Audited Agent", border_style="dim"))

        # Recommendations table
        actionable = [c for c in report.ranked_candidates if c.dominance and c.dominance.dominates]
        non_actionable = [c for c in report.ranked_candidates if not (c.dominance and c.dominance.dominates)]

        if not actionable:
            self._console.print(
                "[bold green]✓ No better alternative found.[/bold green]  "
                "Your current setup wins on its own terms — or the KB didn't have enough data."
            )
        else:
            table = Table(
                title=f"Recommendations ({len(actionable)} actionable)",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Rank", style="dim", width=5)
            table.add_column("Alternative", min_width=22)
            table.add_column("Type", min_width=18)
            table.add_column("Cost Δ", justify="right", min_width=10)
            table.add_column("Reliability Δ", justify="right", min_width=14)
            table.add_column("Complexity Δ", justify="right", min_width=13)
            table.add_column("Verdict")

            for i, c in enumerate(actionable, 1):
                d = c.dominance
                assert d is not None
                table.add_row(
                    str(i),
                    c.name,
                    _fmt_type(c.recommendation_type),
                    _fmt_delta(d.cost_delta_pct, invert=False),
                    _fmt_delta(d.reliability_delta_pct),
                    _fmt_delta(d.complexity_delta_pct),
                    "[green]✓ Dominates[/green]",
                )

            self._console.print(table)

            top = actionable[0]
            self._console.print()
            self._console.print(_candidate_detail_panel(top))

        # Validation results
        if report.validation_results:
            self._console.print()
            self._console.rule("Empirical Validation", style="yellow")
            for vr in report.validation_results:
                color = {"passed": "green", "failed": "red", "error": "red"}.get(vr.status.value, "yellow")
                self._console.print(
                    f"  [{color}]{vr.status.value.upper()}[/{color}]  "
                    f"[bold]{vr.candidate_id}[/bold]  "
                    + (f"— confirmed dominates: {vr.confirmed_dominates}" if vr.confirmed_dominates is not None else "")
                    + (f"\n  [red]{vr.error_message}[/red]" if vr.error_message else "")
                )

        # KB metadata footer
        self._console.print()
        self._console.print(
            f"[dim]KB snapshot: {report.kb_snapshot_date or 'unknown'} · "
            f"Candidates evaluated: {report.total_candidates_evaluated}[/dim]"
        )

        return ""  # console.print() side-effects; return empty for capture

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def _render_json(self, report: AlternativesReport) -> str:
        return report.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Summary (CI-friendly single line)
    # ------------------------------------------------------------------

    def _render_summary(self, report: AlternativesReport) -> str:
        top = report.top_recommendation
        if top is None:
            return "AgentCheck v0.4: no actionable alternative found."
        return (
            f"AgentCheck v0.4: switch to {top.name} "
            f"({top.dominance.winning_axes[0] if top.dominance else '?'} improvement). "
            f"{top.dominance.reason if top.dominance else ''}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_type(rec_type: RecommendationType) -> str:
    labels = {
        RecommendationType.FRAMEWORK_SHIFT: "Framework Shift",
        RecommendationType.PATTERN_SHIFT: "Pattern Shift",
        RecommendationType.ARCHITECTURAL_SHIFT: "Architectural Shift",
        RecommendationType.MODEL_DOWNGRADE: "Model Downgrade",
        RecommendationType.DELETE_THE_LLM: "Delete the LLM",
    }
    return labels.get(rec_type, rec_type.value)


def _fmt_delta(value: float | None, invert: bool = True) -> str:
    """Format a percentage delta.  Green if positive (better), red if negative."""
    if value is None:
        return "[dim]n/a[/dim]"
    sign = "+" if value >= 0 else ""
    color = "green" if value >= 0 else "red"
    return f"[{color}]{sign}{value:.1f} %[/{color}]"


def _candidate_detail_panel(candidate: AlternativeCandidate) -> "Panel":
    from rich.panel import Panel  # type: ignore[import]

    lines = [f"[bold]{candidate.name}[/bold]  ({_fmt_type(candidate.recommendation_type)})"]
    if candidate.description:
        lines.append("")
        lines.append(candidate.description[:300])
    if candidate.dominance:
        d = candidate.dominance
        lines.append("")
        lines.append(f"[italic]{d.reason}[/italic]")
    if candidate.code_example:
        lines.append("")
        lines.append("[bold]Suggested replacement:[/bold]")
        lines.append(f"[green]{candidate.code_example}[/green]")
    if candidate.evidence_url:
        lines.append("")
        lines.append(f"[dim]Evidence: {candidate.evidence_url}[/dim]")

    return Panel("\n".join(lines), title="Top Recommendation", border_style="green")
