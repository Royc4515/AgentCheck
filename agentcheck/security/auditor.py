"""Agent-Auditor: static analysis over the target agent source file."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_LIB_PATH = Path(__file__).parent / "attack_library.yaml"


@dataclass
class Finding:
    id: str
    pattern_id: str
    severity: str  # critical | high | medium | low
    title: str
    description: str
    line: int
    snippet: str
    cwe: str = ""
    classification: str = ""  # filled in later by risk_classifier
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "line": self.line,
            "snippet": self.snippet,
            "cwe": self.cwe,
            "classification": self.classification,
            "rationale": self.rationale,
        }


@dataclass
class AuditReport:
    agent_path: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            if f.severity in out:
                out[f.severity] += 1
        return out

    @property
    def risk_factor(self) -> int:
        """1 = clean, 10 = catastrophic."""
        c = self.counts
        weighted = c["critical"] * 4 + c["high"] * 2 + c["medium"] * 1 + c["low"] * 0.5
        return int(max(1, min(10, round(1 + weighted))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_path": self.agent_path,
            "risk_factor": self.risk_factor,
            "counts": self.counts,
            "findings": [f.to_dict() for f in self.findings],
        }


def _load_patterns() -> list[dict[str, Any]]:
    data = yaml.safe_load(_LIB_PATH.read_text(encoding="utf-8"))
    return data.get("patterns", [])


def audit_source(agent_path: Path) -> AuditReport:
    """Scan ``agent_path`` against the static attack library."""
    agent_path = Path(agent_path).resolve()
    source = agent_path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    patterns = _load_patterns()

    findings: list[Finding] = []
    counter = 0
    for pat in patterns:
        regex = re.compile(pat["regex"])
        for lineno, line in enumerate(lines, start=1):
            for match in regex.finditer(line):
                counter += 1
                findings.append(
                    Finding(
                        id=f"S{counter:03d}",
                        pattern_id=pat["id"],
                        severity=pat["severity"],
                        title=pat["title"],
                        description=pat["description"],
                        line=lineno,
                        snippet=line.strip()[:200],
                        cwe=pat.get("cwe", ""),
                    )
                )

    return AuditReport(agent_path=str(agent_path), findings=findings)
