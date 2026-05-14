#!/usr/bin/env python
"""Refresh the AgentCheck KB with live data.

Usage::

    python scripts/refresh_kb.py
    GITHUB_TOKEN=ghp_xxx python scripts/refresh_kb.py   # for 5000 req/hr instead of 60

Fetches GitHub maintenance signals and OpenRouter pricing, then rewrites the
KB YAMLs in place.  Run again whenever you want a fresh snapshot.
"""

import os
import sys

from agentcheck.alternatives.kb_refresher import (
    GitHubSource,
    KBRefresher,
    OpenRouterPricingSource,
)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "[!] No GITHUB_TOKEN set — using the 60 req/hr anonymous rate limit.\n"
            "    Set GITHUB_TOKEN to a personal access token for 5000 req/hr.",
            file=sys.stderr,
        )

    refresher = KBRefresher(
        github=GitHubSource(token=token),
        pricing=OpenRouterPricingSource(),
    )
    summary = refresher.refresh_all()
    print(summary.report())
    return 0 if not summary.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
