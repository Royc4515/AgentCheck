"""Tests for the KB refresher.

HTTP calls are fully mocked — these tests verify the parsing, the YAML
rewrite, the provenance tagging, and the cost-per-task projection math.
"""

import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from agentcheck.alternatives.kb_refresher import (
    GitHubSnapshot,
    GitHubSource,
    KBRefresher,
    OpenRouterPricingSource,
    PricingSnapshot,
    _parse_github_repo,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestParseGithubRepo:
    def test_https_url(self) -> None:
        assert _parse_github_repo("https://github.com/pydantic/pydantic-ai") == (
            "pydantic", "pydantic-ai"
        )

    def test_url_with_dotgit_suffix(self) -> None:
        assert _parse_github_repo("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_url_with_path(self) -> None:
        assert _parse_github_repo("https://github.com/o/r/tree/main") == ("o", "r")

    def test_non_github_url_returns_none(self) -> None:
        assert _parse_github_repo("https://gitlab.com/x/y") is None

    def test_empty_returns_none(self) -> None:
        assert _parse_github_repo("") is None


class TestPricingSnapshot:
    def test_cost_per_task_default_token_assumptions(self) -> None:
        # $0.003/1k prompt + $0.015/1k completion on a 2k+500 task
        # = 0.003 * 2 + 0.015 * 0.5 = 0.006 + 0.0075 = 0.0135
        snap = PricingSnapshot(
            model_id="x", prompt_usd_per_1k=0.003, completion_usd_per_1k=0.015
        )
        assert snap.cost_per_task() == pytest.approx(0.0135)

    def test_cost_per_task_custom_tokens(self) -> None:
        snap = PricingSnapshot(
            model_id="x", prompt_usd_per_1k=0.001, completion_usd_per_1k=0.002
        )
        # 1k input * 0.001 + 1k output * 0.002 = 0.003
        assert snap.cost_per_task(input_tokens=1000, output_tokens=1000) == pytest.approx(0.003)


class TestGitHubSnapshotHealth:
    def test_archived_is_archived(self) -> None:
        snap = GitHubSnapshot(
            open_issues=10, last_release_days_ago=5, pushed_days_ago=2,
            archived=True, stars=100,
        )
        assert snap.health == "archived"

    def test_stagnant_when_pushed_over_180_days(self) -> None:
        snap = GitHubSnapshot(
            open_issues=10, last_release_days_ago=300, pushed_days_ago=200,
            archived=False, stars=100,
        )
        assert snap.health == "stagnant"

    def test_active(self) -> None:
        snap = GitHubSnapshot(
            open_issues=10, last_release_days_ago=5, pushed_days_ago=2,
            archived=False, stars=100,
        )
        assert snap.health == "active"


# ---------------------------------------------------------------------------
# Refresher end-to-end with mocked sources
# ---------------------------------------------------------------------------

@pytest.fixture()
def kb_with_one_entry(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    (kb / "frameworks").mkdir(parents=True)
    yaml_path = kb / "frameworks" / "pydanticai.yaml"
    yaml_path.write_text(
        yaml.safe_dump({
            "id": "pydanticai",
            "name": "PydanticAI",
            "type": "framework",
            "snapshot_date": "2024-01-01",
            "pricing_model": "anthropic/claude-sonnet-4.5",
            "metrics": {
                "reliability_score": 0.81,
                "cost_per_task_usd": 0.028,
                "loc_estimate": 90,
                "cyclomatic_complexity": 11,
            },
            "strengths": ["Type safe"],
            "weaknesses": ["Small ecosystem"],
            "evidence_url": "https://github.com/pydantic/pydantic-ai",
            "data_provenance": {
                "metrics.reliability_score": "estimate",
                "metrics.cost_per_task_usd": "estimate",
            },
        }),
        encoding="utf-8",
    )
    return kb


@pytest.fixture()
def mock_github() -> MagicMock:
    src = MagicMock(spec=GitHubSource)
    src.fetch.return_value = GitHubSnapshot(
        open_issues=342,
        last_release_days_ago=7,
        pushed_days_ago=1,
        archived=False,
        stars=12500,
    )
    return src


@pytest.fixture()
def mock_pricing() -> MagicMock:
    src = MagicMock(spec=OpenRouterPricingSource)
    src.get.return_value = PricingSnapshot(
        model_id="anthropic/claude-sonnet-4.5",
        prompt_usd_per_1k=0.003,
        completion_usd_per_1k=0.015,
    )
    return src


class TestKBRefresher:
    def test_updates_maintenance_block_from_github(
        self, kb_with_one_entry: Path, mock_github, mock_pricing
    ) -> None:
        KBRefresher(kb_root=kb_with_one_entry, github=mock_github, pricing=mock_pricing).refresh_all()

        raw = yaml.safe_load((kb_with_one_entry / "frameworks" / "pydanticai.yaml").read_text())
        assert raw["maintenance"]["open_issues"] == 342
        assert raw["maintenance"]["stars"] == 12500
        assert raw["maintenance"]["health"] == "active"
        assert raw["maintenance"]["archived"] is False

    def test_updates_cost_from_openrouter(
        self, kb_with_one_entry: Path, mock_github, mock_pricing
    ) -> None:
        KBRefresher(kb_root=kb_with_one_entry, github=mock_github, pricing=mock_pricing).refresh_all()

        raw = yaml.safe_load((kb_with_one_entry / "frameworks" / "pydanticai.yaml").read_text())
        # 2k input * 0.003/1k + 500 output * 0.015/1k = 0.006 + 0.0075 = 0.0135
        assert raw["metrics"]["cost_per_task_usd"] == pytest.approx(0.0135)

    def test_writes_provenance_tags(
        self, kb_with_one_entry: Path, mock_github, mock_pricing
    ) -> None:
        KBRefresher(kb_root=kb_with_one_entry, github=mock_github, pricing=mock_pricing).refresh_all()

        raw = yaml.safe_load((kb_with_one_entry / "frameworks" / "pydanticai.yaml").read_text())
        prov = raw["data_provenance"]
        today = datetime.date.today().isoformat()
        assert prov["metrics.cost_per_task_usd"] == f"openrouter_{today}"
        assert prov["maintenance.open_issues"].startswith("github_")
        # Estimates that weren't touched stay as estimate
        assert prov["metrics.reliability_score"] == "estimate"

    def test_preserves_qualitative_fields(
        self, kb_with_one_entry: Path, mock_github, mock_pricing
    ) -> None:
        KBRefresher(kb_root=kb_with_one_entry, github=mock_github, pricing=mock_pricing).refresh_all()
        raw = yaml.safe_load((kb_with_one_entry / "frameworks" / "pydanticai.yaml").read_text())
        assert raw["strengths"] == ["Type safe"]
        assert raw["weaknesses"] == ["Small ecosystem"]

    def test_skips_entry_with_no_github_and_no_pricing(
        self, tmp_path: Path, mock_github, mock_pricing
    ) -> None:
        kb = tmp_path / "kb"
        (kb / "patterns").mkdir(parents=True)
        (kb / "patterns" / "abstract.yaml").write_text(
            yaml.safe_dump({"id": "x", "name": "X", "type": "pattern"}),
            encoding="utf-8",
        )
        summary = KBRefresher(kb_root=kb, github=mock_github, pricing=mock_pricing).refresh_all()
        assert summary.updated == []
        assert len(summary.skipped) == 1

    def test_pricing_model_unknown_is_skipped_gracefully(
        self, kb_with_one_entry: Path, mock_github
    ) -> None:
        pricing = MagicMock(spec=OpenRouterPricingSource)
        pricing.get.return_value = None  # model not in catalog
        KBRefresher(kb_root=kb_with_one_entry, github=mock_github, pricing=pricing).refresh_all()
        raw = yaml.safe_load((kb_with_one_entry / "frameworks" / "pydanticai.yaml").read_text())
        # cost not overwritten when pricing source returns None
        assert raw["metrics"]["cost_per_task_usd"] == 0.028

    def test_summary_collects_errors(
        self, kb_with_one_entry: Path, mock_pricing
    ) -> None:
        github = MagicMock(spec=GitHubSource)
        github.fetch.side_effect = RuntimeError("rate limit")
        summary = KBRefresher(
            kb_root=kb_with_one_entry, github=github, pricing=mock_pricing
        ).refresh_all()
        assert len(summary.errors) == 1
        assert "rate limit" in summary.errors[0][1]
