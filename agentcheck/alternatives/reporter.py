from __future__ import annotations

"""Rich terminal reporter for check #4 — Alternatives.

Three output modes:
  terminal  — Rich-styled side-by-side comparison table (default)
  json      — Machine-readable JSON dump
  summary   — Single-line verdict for CI pipelines
"""

from typing import Literal, Optional

from .models import (
    AlternativeCandidate,
    CandidateComparison,
    FullComparisonReport,
    RecommendationType,
)

OutputMode = Literal["terminal", "json", "summary"]

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


class AlternativesReporter:
    """Renders a FullComparisonReport to the requested output mode."""

    def __init__(self, mode: OutputMode = "terminal") -> None:
        self._mode = mode
        self._console = Console() if _RICH_AVAILABLE else None

    def render(self, report: FullComparisonReport) -> str:
        if self._mode == "json":
            return self._render_json(report)
        if self._mode == "summary":
            return self._render_summary(report)
        return self._render_terminal(report)

    # ------------------------------------------------------------------
    # Terminal (Rich)
    # ------------------------------------------------------------------

    def _render_terminal(self, report: FullComparisonReport) -> str:
        if not _RICH_AVAILABLE:
            return self._render_summary(report)

        assert self._console is not None
        self._console.print()
        self._console.print(
            "[bold cyan]AgentCheck v0.4[/bold cyan] — "
            "[italic]Does a better agent exist?[/italic]"
        )
        self._console.rule(style="cyan")

        self._print_profile(report)

        if not report.comparisons:
            self._console.print(
                "[bold green]✓ No better alternative found.[/bold green]  "
                "The KB has nothing that clears your bar — or your agent is already great."
            )
        else:
            self._print_comparison_table(report)
            self._print_top_detail(report.comparisons[0])

        self._console.print()
        self._console.print(
            f"[dim]KB snapshot: {report.kb_snapshot_date} · "
            f"Candidates evaluated: {report.total_candidates_evaluated}[/dim]"
        )
        return ""

    def _print_profile(self, report: FullComparisonReport) -> None:
        assert self._console is not None
        p = report.agent_profile
        lines = []
        if p.framework:
            lines.append(
                f"Framework  : [bold]{p.framework}[/bold] "
                f"(confidence {p.framework_confidence:.0%})"
            )
        if p.task_completion_rate is not None:
            lines.append(
                f"Reliability: [bold]{p.task_completion_rate:.0%}[/bold] task completion"
            )
        if p.cost_per_task_usd is not None:
            lines.append(f"Cost/task  : [bold]${p.cost_per_task_usd:.4f}[/bold]")
        if p.loc is not None:
            lines.append(f"LOC        : [bold]{p.loc}[/bold]")
        if p.security_finding_count is not None:
            color = "red" if p.security_finding_count > 0 else "green"
            lines.append(
                f"Security   : [{color}]{p.security_finding_count} findings[/{color}]"
            )
        if lines:
            self._console.print(
                Panel("\n".join(lines), title="Audited Agent", border_style="dim")
            )

    def _print_comparison_table(self, report: FullComparisonReport) -> None:
        assert self._console is not None

        table = Table(
            title=f"Top {len(report.comparisons)} Alternatives",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Metric", style="dim", min_width=14)
        table.add_column("Current", justify="right", min_width=12)

        for comp in report.comparisons:
            label = f"[bold]{comp.candidate.name}[/bold]"
            if comp.candidate.dominance and comp.candidate.dominance.dominates:
                label += " [green]✓[/green]"
            table.add_column(label, justify="right", min_width=16)

        # Reliability row
        table.add_row(
            "Reliability",
            _fmt_pct(report.comparisons[0].original_reliability if report.comparisons else None),
            *[_fmt_pct(c.alt_reliability) for c in report.comparisons],
        )

        # Cost row
        table.add_row(
            "Cost / task",
            _fmt_usd(report.comparisons[0].original_cost if report.comparisons else None),
            *[_fmt_usd(c.alt_cost) for c in report.comparisons],
        )

        # LOC row
        table.add_row(
            "LOC",
            _fmt_int(report.comparisons[0].original_loc if report.comparisons else None),
            *[_fmt_int(c.alt_loc) for c in report.comparisons],
        )

        # Security row
        table.add_row(
            "Sec findings",
            _fmt_int(
                report.comparisons[0].original_security_findings
                if report.comparisons
                else None,
                lower_is_better=True,
            ),
            *[
                _fmt_int(c.alt_security_findings, lower_is_better=True)
                for c in report.comparisons
            ],
        )

        # Verdict row
        table.add_row(
            "Verdict",
            "[dim]current[/dim]",
            *[_fmt_verdict(c) for c in report.comparisons],
        )

        self._console.print(table)

    def _print_top_detail(self, comp: CandidateComparison) -> None:
        assert self._console is not None
        c = comp.candidate
        lines = [f"[bold]{c.name}[/bold]  ({_fmt_type(c.recommendation_type)})"]

        if c.description:
            lines.append("")
            lines.append(c.description[:300])

        if c.dominance:
            lines.append("")
            lines.append(f"[italic]{c.dominance.reason}[/italic]")

        if c.code_example:
            lines.append("")
            lines.append("[bold]Suggested replacement:[/bold]")
            lines.append(f"[green]{c.code_example}[/green]")

        if c.evidence_url:
            lines.append("")
            lines.append(f"[dim]Evidence: {c.evidence_url}[/dim]")

        border = "green" if (c.dominance and c.dominance.dominates) else "yellow"
        self._console.print(
            Panel("\n".join(lines), title="Top Recommendation", border_style=border)
        )

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def _render_json(self, report: FullComparisonReport) -> str:
        return report.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _render_summary(self, report: FullComparisonReport) -> str:
        top = report.top_recommendation
        if top is None:
            return "AgentCheck v0.4: no actionable alternative found."
        axis = top.dominance.winning_axes[0] if top.dominance else "?"
        reason = top.dominance.reason if top.dominance else ""
        return f"AgentCheck v0.4: switch to {top.name} ({axis} improvement). {reason}"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_pct(v: Optional[float]) -> str:
    return f"{v:.0%}" if v is not None else "[dim]n/a[/dim]"


def _fmt_usd(v: Optional[float]) -> str:
    return f"${v:.4f}" if v is not None else "[dim]n/a[/dim]"


def _fmt_int(v: Optional[int], lower_is_better: bool = False) -> str:
    if v is None:
        return "[dim]n/a[/dim]"
    return str(v)


def _fmt_verdict(comp: CandidateComparison) -> str:
    d = comp.candidate.dominance
    if d is None:
        return "[dim]not evaluated[/dim]"
    if d.dominates:
        axes = ", ".join(d.winning_axes)
        return f"[green]✓ wins on {axes}[/green]"
    if d.regressed_axes:
        axes = ", ".join(d.regressed_axes)
        return f"[red]✗ regresses {axes}[/red]"
    return "[yellow]~ no clear win[/yellow]"


def _fmt_type(rec_type: RecommendationType) -> str:
    return {
        RecommendationType.FRAMEWORK_SHIFT: "Framework Shift",
        RecommendationType.PATTERN_SHIFT: "Pattern Shift",
        RecommendationType.ARCHITECTURAL_SHIFT: "Architectural Shift",
        RecommendationType.MODEL_DOWNGRADE: "Model Downgrade",
        RecommendationType.DELETE_THE_LLM: "Delete the LLM",
    }.get(rec_type, rec_type.value)
