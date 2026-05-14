"""Part 3 — Security runner.

Reads the target agent source from ``agent_path`` (the path IS the
"targetAgents" input — no filename assumption), runs the static auditor,
asks the LLM to classify each finding as necessary or unnecessary, and
writes ``security_result.json`` plus a timestamped per-run report.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from agentcheck.alternatives.models import SecurityResult
from agentcheck.shared import ensure_results_dir, write_json

from .auditor import audit_source
from .risk_classifier import classify_findings


def _infer_purpose(source: str) -> str:
    m = re.search(r'"""(.+?)"""', source, re.DOTALL)
    if m:
        return m.group(1).strip().splitlines()[0]
    return "unspecified AI agent"


def run_security(agent_path: Path, results_dir: Path) -> SecurityResult:
    """Run the Part 3 security audit against the agent at ``agent_path``."""
    agent_path = Path(agent_path).resolve()
    results_dir = ensure_results_dir(Path(results_dir))

    report = audit_source(agent_path)
    source = agent_path.read_text(encoding="utf-8", errors="replace")
    purpose = _infer_purpose(source)
    classify_findings(report.findings, agent_purpose=purpose)

    counts = report.counts

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    reports_dir = results_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamped = reports_dir / f"security_{timestamp}.json"
    timestamped.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    result = SecurityResult(
        is_safe=(counts["critical"] + counts["high"] == 0),
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
        finding_ids=[f.id for f in report.findings],
        hardcoded_secrets=any(
            f.pattern_id in {"HARDCODED_API_KEY", "HARDCODED_PASSWORD"}
            for f in report.findings
        ),
        prompt_injection_vulnerable=any(
            f.pattern_id == "PROMPT_INJECTION_SINK" for f in report.findings
        ),
        unsafe_deserialization=any(
            f.pattern_id == "UNSAFE_DESERIALIZATION" for f in report.findings
        ),
    )

    out_path = results_dir / "security_result.json"
    write_json(out_path, result)
    print(
        f"[security] risk_factor={report.risk_factor}/10 "
        f"(crit={counts['critical']} high={counts['high']} "
        f"med={counts['medium']} low={counts['low']}) — wrote {out_path.name}"
    )
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("agent_path", type=Path)
    parser.add_argument("--results-dir", type=Path, default=Path(".agentcheck"))
    args = parser.parse_args()
    run_security(args.agent_path, args.results_dir)
