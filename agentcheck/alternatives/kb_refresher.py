from __future__ import annotations

"""KB refresher — pulls live data into the YAML knowledge base.

Sources (all free, no auth required):
  GitHub REST API   → maintenance signals (open_issues, releases, archived, stars)
  PyPI JSON API     → latest release date / version cross-check
  OpenRouter API    → per-model prompt/completion pricing in USD-per-token

Run via the CLI::

    python -m agentcheck.alternatives.scripts.refresh_kb

The refresher is non-destructive: it preserves the qualitative fields
(strengths, weaknesses, best_fit_patterns, ...) and only updates the
measured metric fields + writes a ``data_provenance`` block recording
which fields came from a live source vs. remained as estimates.
"""

import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests
import yaml

_USER_AGENT = "agentcheck-kb-refresher/0.4"
_GITHUB_API = "https://api.github.com"
_PYPI_API = "https://pypi.org/pypi"
_OPENROUTER_API = "https://openrouter.ai/api/v1/models"

# Token assumptions for cost projection — documented in SDD §4.2.
# An "average task" is 2000 input tokens + 500 output tokens.
_AVG_INPUT_TOKENS = 2000
_AVG_OUTPUT_TOKENS = 500

_GH_REPO_RE = re.compile(r"github\.com/([^/]+)/([^/#?]+)")


# ---------------------------------------------------------------------------
# Source-level dataclasses (one fetch = one of these)
# ---------------------------------------------------------------------------

@dataclass
class GitHubSnapshot:
    open_issues: int
    last_release_days_ago: Optional[int]
    pushed_days_ago: int
    archived: bool
    stars: int

    @property
    def health(self) -> str:
        if self.archived:
            return "archived"
        if self.pushed_days_ago > 180:
            return "stagnant"
        return "active"


@dataclass
class PricingSnapshot:
    model_id: str
    prompt_usd_per_1k: float
    completion_usd_per_1k: float

    def cost_per_task(
        self,
        input_tokens: int = _AVG_INPUT_TOKENS,
        output_tokens: int = _AVG_OUTPUT_TOKENS,
    ) -> float:
        return round(
            (self.prompt_usd_per_1k * input_tokens / 1000)
            + (self.completion_usd_per_1k * output_tokens / 1000),
            6,
        )


# ---------------------------------------------------------------------------
# HTTP fetchers — each isolated so they can be swapped / mocked in tests
# ---------------------------------------------------------------------------

class GitHubSource:
    """Wraps the GitHub REST API. Auth via $GITHUB_TOKEN if set (5000 req/hr)."""

    def __init__(self, token: Optional[str] = None, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/vnd.github+json",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def fetch(self, owner: str, repo: str) -> GitHubSnapshot:
        repo_url = f"{_GITHUB_API}/repos/{owner}/{repo}"
        release_url = f"{repo_url}/releases/latest"

        repo_data = self._get_json(repo_url)
        release_data = self._get_json(release_url, allow_404=True)

        pushed_days = _days_since(repo_data.get("pushed_at"))
        release_days = (
            _days_since(release_data.get("published_at")) if release_data else None
        )

        return GitHubSnapshot(
            open_issues=int(repo_data.get("open_issues_count", 0)),
            last_release_days_ago=release_days,
            pushed_days_ago=pushed_days if pushed_days is not None else 9999,
            archived=bool(repo_data.get("archived", False)),
            stars=int(repo_data.get("stargazers_count", 0)),
        )

    def _get_json(self, url: str, allow_404: bool = False) -> dict[str, Any]:
        resp = requests.get(url, headers=self._headers, timeout=self._timeout)
        if allow_404 and resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()


class OpenRouterPricingSource:
    """Reads the public OpenRouter model catalog (no auth required)."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._cache: Optional[dict[str, PricingSnapshot]] = None

    def all_models(self) -> dict[str, PricingSnapshot]:
        if self._cache is not None:
            return self._cache
        resp = requests.get(
            _OPENROUTER_API,
            headers={"User-Agent": _USER_AGENT},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        models: dict[str, PricingSnapshot] = {}
        for entry in data:
            model_id = entry.get("id")
            pricing = entry.get("pricing", {})
            try:
                prompt = float(pricing.get("prompt", 0))
                completion = float(pricing.get("completion", 0))
            except (TypeError, ValueError):
                continue
            if not model_id:
                continue
            # OpenRouter reports USD-per-token; convert to USD-per-1k for readability
            models[model_id] = PricingSnapshot(
                model_id=model_id,
                prompt_usd_per_1k=round(prompt * 1000, 6),
                completion_usd_per_1k=round(completion * 1000, 6),
            )
        self._cache = models
        return models

    def get(self, model_id: str) -> Optional[PricingSnapshot]:
        return self.all_models().get(model_id)


# ---------------------------------------------------------------------------
# Refresher — walks the KB directory and updates each YAML file in place
# ---------------------------------------------------------------------------

@dataclass
class RefreshSummary:
    updated: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (file, reason)
    errors: list[tuple[str, str]] = field(default_factory=list)   # (file, error)

    def report(self) -> str:
        lines = [
            f"Updated: {len(self.updated)}",
            f"Skipped: {len(self.skipped)}",
            f"Errors:  {len(self.errors)}",
        ]
        for f in self.updated:
            lines.append(f"  ✓ {f}")
        for f, reason in self.skipped:
            lines.append(f"  · {f}  ({reason})")
        for f, err in self.errors:
            lines.append(f"  ✗ {f}  {err}")
        return "\n".join(lines)


class KBRefresher:
    """Orchestrates one full pass over the KB.

    For each YAML entry:
      1. Parse evidence_url for a GitHub owner/repo  → GitHubSource
      2. Read the entry's pricing_model field        → OpenRouterPricingSource
      3. Write fetched values back into the YAML + a data_provenance block

    The refresher never touches qualitative fields (strengths, weaknesses,
    best_fit_patterns, detection_signatures, code examples).
    """

    def __init__(
        self,
        kb_root: Optional[Path] = None,
        github: Optional[GitHubSource] = None,
        pricing: Optional[OpenRouterPricingSource] = None,
    ) -> None:
        self._kb_root = kb_root or (Path(__file__).parent / "kb")
        self._github = github or GitHubSource()
        self._pricing = pricing or OpenRouterPricingSource()

    def refresh_all(self) -> RefreshSummary:
        summary = RefreshSummary()
        for yaml_path in sorted(self._kb_root.rglob("*.yaml")):
            try:
                result = self._refresh_one(yaml_path)
            except Exception as exc:  # noqa: BLE001 — best-effort across many files
                summary.errors.append((yaml_path.name, f"{type(exc).__name__}: {exc}"))
                continue

            if result == "updated":
                summary.updated.append(yaml_path.name)
            else:
                summary.skipped.append((yaml_path.name, result))
        return summary

    # ------------------------------------------------------------------

    def _refresh_one(self, yaml_path: Path) -> str:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        provenance: dict[str, str] = dict(raw.get("data_provenance", {}))
        today = datetime.date.today().isoformat()

        touched = False

        # --- GitHub maintenance signals ---
        owner_repo = _parse_github_repo(raw.get("evidence_url", ""))
        if owner_repo:
            owner, repo = owner_repo
            snap = self._github.fetch(owner, repo)
            maintenance = raw.setdefault("maintenance", {})
            maintenance["open_issues"] = snap.open_issues
            maintenance["last_release_days_ago"] = snap.last_release_days_ago
            maintenance["pushed_days_ago"] = snap.pushed_days_ago
            maintenance["archived"] = snap.archived
            maintenance["stars"] = snap.stars
            maintenance["health"] = snap.health
            for f in (
                "open_issues",
                "last_release_days_ago",
                "archived",
                "stars",
                "health",
            ):
                provenance[f"maintenance.{f}"] = f"github_{today}"
            touched = True

        # --- Pricing ---
        pricing_model = raw.get("pricing_model")
        if pricing_model:
            snap = self._pricing.get(pricing_model)
            if snap is not None:
                metrics = raw.setdefault("metrics", {})
                metrics["cost_per_task_usd"] = snap.cost_per_task()
                metrics["_pricing_model"] = pricing_model
                metrics["_prompt_usd_per_1k"] = snap.prompt_usd_per_1k
                metrics["_completion_usd_per_1k"] = snap.completion_usd_per_1k
                provenance["metrics.cost_per_task_usd"] = f"openrouter_{today}"
                touched = True

        if not touched:
            return "no live fields (no evidence_url + no pricing_model)"

        raw["data_provenance"] = provenance
        raw["snapshot_date"] = today
        yaml_path.write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return "updated"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_github_repo(url: str) -> Optional[tuple[str, str]]:
    if not url:
        return None
    m = _GH_REPO_RE.search(url)
    if not m:
        return None
    repo = m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return (m.group(1), repo)


def _days_since(iso_timestamp: Optional[str]) -> Optional[int]:
    if not iso_timestamp:
        return None
    try:
        dt = datetime.datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    delta = datetime.datetime.now(datetime.timezone.utc) - dt
    return max(0, delta.days)
