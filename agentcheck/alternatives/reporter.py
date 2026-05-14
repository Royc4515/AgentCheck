from __future__ import annotations

"""Rich terminal reporter for check #4 — Alternatives.

Three output modes:
  terminal  — Rich-styled score panel + alternatives with pros/cons (default)
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
    from rich.columns import Columns
    from rich.text import Text

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
    # Terminal
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

        self._print_overall_score(report)
        self._print_alternatives(report)

        self._console.print()
        self._console.print(
            f"[dim]KB snapshot: {report.kb_snapshot_date} · "
            f"Candidates evaluated: {report.total_candidates_evaluated}[/dim]"
        )
        return ""

    def _print_overall_score(self, report: FullComparisonReport) -> None:
        assert self._console is not None
        s = report.overall_score
        if s is None or s.overall_grade is None:
            return

        grade_color = _grade_color(s.overall_grade.value)

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Check", style="dim", min_width=14)
        table.add_column("Score", justify="right", min_width=8)
        table.add_column("Grade", justify="center", min_width=6)

        if s.reliability_score is not None:
            table.add_row(
                "#1 Reliability",
                f"{s.reliability_score:.0f} / 100",
                _grade_badge(s.reliability_grade),
            )
        if s.efficiency_score is not None:
            table.add_row(
                "#2 Efficiency",
                f"{s.efficiency_score:.0f} / 100",
                _grade_badge(s.efficiency_grade),
            )
        if s.security_score is not None:
            table.add_row(
                "#3 Security",
                f"{s.security_score:.0f} / 100",
                _grade_badge(s.security_grade),
            )
        table.add_row("", "", "")
        table.add_row(
            "[bold]Overall[/bold]",
            f"[bold]{s.overall_score:.0f} / 100[/bold]",
            f"[{grade_color}][bold]{s.overall_grade.value}[/bold][/{grade_color}]",
        )

        self._console.print(Panel(table, title="AgentCheck Score", border_style=grade_color))

    def _print_alternatives(self, report: FullComparisonReport) -> None:
        assert self._console is not None

        if not report.comparisons:
            self._console.print(
                "\n[bold green]✓ No alternatives suggested.[/bold green]  "
                "Your current setup fits the available KB data well."
            )
            return

        self._console.print()
        self._console.print(
            f"[bold]Suggested Alternatives[/bold] "
            f"[dim](based on KB data — not empirically verified)[/dim]"
        )
        self._console.print()

        for i, comp in enumerate(report.comparisons, 1):
            self._print_candidate_card(i, comp)

    def _print_candidate_card(self, rank: int, comp: CandidateComparison) -> None:
        assert self._console is not None
        c = comp.candidate
        d = c.dominance

        # Header line
        rec_label = ""
        border = "dim"
        if d and d.recommended:
            rec_label = "  [green]✓ Recommended[/green]"
            border = "green"
        elif d and d.worse_on:
            rec_label = f"  [yellow]⚠ Trade-offs on {', '.join(d.worse_on)}[/yellow]"
            border = "yellow"

        lines: list[str] = []

        # Type badge
        lines.append(f"[dim]{_fmt_type(c.recommendation_type)}[/dim]{rec_label}")
        lines.append("")

        # Description
        if c.description:
            lines.append(c.description.strip()[:200])
            lines.append("")

        # Trade-off summary from matching engine
        if d and d.trade_off_summary:
            lines.append(f"[italic]{d.trade_off_summary}[/italic]")
            lines.append("")

        # Pros
        if c.strengths:
            lines.append("[green]Strengths[/green]")
            for s in c.strengths[:4]:
                lines.append(f"  [green]+[/green] {s}")
            lines.append("")

        # Cons
        if c.weaknesses:
            lines.append("[red]Weaknesses[/red]")
            for w in c.weaknesses[:3]:
                lines.append(f"  [red]−[/red] {w}")
            lines.append("")

        # Key metrics (KB-sourced) — each tagged with data provenance
        prov = c.data_provenance
        metrics_parts = []
        if comp.alt_reliability is not None:
            metrics_parts.append(
                f"Reliability {comp.alt_reliability:.0%} {_badge(prov.get('metrics.reliability_score'))}"
            )
        if comp.alt_cost is not None:
            metrics_parts.append(
                f"Cost ${comp.alt_cost:.4f}/task {_badge(prov.get('metrics.cost_per_task_usd'))}"
            )
        if comp.alt_loc is not None:
            metrics_parts.append(
                f"~{comp.alt_loc} LOC {_badge(prov.get('metrics.loc_estimate'))}"
            )
        if metrics_parts:
            lines.append(f"[dim]KB data: {' · '.join(metrics_parts)}[/dim]")

        # Code example
        if c.code_example:
            lines.append("")
            lines.append("[bold]Example:[/bold]")
            lines.append(f"[green]{c.code_example}[/green]")

        # Evidence link
        if c.evidence_url:
            lines.append("")
            lines.append(f"[dim]{c.evidence_url}[/dim]")

        self._console.print(
            Panel(
                "\n".join(lines),
                title=f"#{rank}  {c.name}",
                border_style=border,
            )
        )

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def _render_json(self, report: FullComparisonReport) -> str:
        return report.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Summary (CI-friendly)
    # ------------------------------------------------------------------

    def _render_summary(self, report: FullComparisonReport) -> str:
        grade = report.overall_score.overall_grade.value if (
            report.overall_score and report.overall_score.overall_grade
        ) else "?"

        if not report.comparisons:
            return f"AgentCheck v0.4: Overall {grade}. No alternatives suggested."

        names = [c.candidate.name for c in report.comparisons]
        return (
            f"AgentCheck v0.4: Overall {grade}. "
            f"Suggested alternatives: {', '.join(names)}."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade_color(grade: str) -> str:
    return {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "bold red"}.get(
        grade, "white"
    )


def _grade_badge(grade) -> str:
    if grade is None:
        return "[dim]n/a[/dim]"
    color = _grade_color(grade.value)
    return f"[{color}]{grade.value}[/{color}]"


def _badge(provenance_tag: Optional[str]) -> str:
    """Render a provenance badge for a metric.

    Tags starting with "github_" / "openrouter_" / "radon_" are measured;
    "estimate" or missing → hand-written.
    """
    if not provenance_tag or provenance_tag == "estimate":
        return "[yellow](est)[/yellow]"
    return "[green](measured)[/green]"


def _fmt_type(rec_type: RecommendationType) -> str:
    return {
        RecommendationType.FRAMEWORK_SHIFT: "Framework Shift",
        RecommendationType.PATTERN_SHIFT: "Pattern Shift",
        RecommendationType.ARCHITECTURAL_SHIFT: "Architectural Shift",
        RecommendationType.MODEL_DOWNGRADE: "Model Downgrade",
        RecommendationType.DELETE_THE_LLM: "Delete the LLM",
    }.get(rec_type, rec_type.value)
