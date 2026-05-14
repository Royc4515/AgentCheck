from __future__ import annotations

"""Loads check #1, #2, #3 JSON outputs into a unified AgentProfile.

Expected file layout (all paths are configurable):
    .agentcheck/
        reliability_result.json    ← produced by check #1
        wastefulness_result.json   ← produced by check #2
        security_result.json       ← produced by check #3

Each file is optional — AgentProfile degrades gracefully when one is absent.
"""

import json
from pathlib import Path
from typing import Optional

from .models import (
    AgentProfile,
    DetectedPattern,
    ReliabilityResult,
    SecurityResult,
    WastefulnessResult,
)

_DEFAULT_DIR = Path(".agentcheck")
_RELIABILITY_FILE = "reliability_result.json"
_WASTEFULNESS_FILE = "wastefulness_result.json"
_SECURITY_FILE = "security_result.json"


class CheckResultNotFound(FileNotFoundError):
    """Raised when a required check JSON file is missing."""


class AgentProfileLoader:
    """Reads the three check JSON files and assembles an AgentProfile.

    Parameters
    ----------
    results_dir:
        Directory containing the check result JSON files.
        Defaults to `.agentcheck/` in the current working directory.
    strict:
        If True, raise CheckResultNotFound when any file is missing.
        If False (default), missing files are silently skipped and the
        corresponding AgentProfile fields are left as None.
    """

    def __init__(
        self,
        results_dir: Optional[Path] = None,
        strict: bool = False,
    ) -> None:
        self._dir = results_dir or _DEFAULT_DIR
        self._strict = strict

    def load(self) -> AgentProfile:
        reliability = self._load_reliability()
        wastefulness = self._load_wastefulness()
        security = self._load_security()

        # Top-level fields are promoted from reliability (primary source)
        framework = None
        framework_confidence = 0.0
        model_id = None
        detected_patterns: list[DetectedPattern] = []

        if reliability:
            framework = reliability.framework
            framework_confidence = reliability.framework_confidence
            model_id = reliability.model_id
            detected_patterns = _parse_patterns(reliability.detected_patterns)

        return AgentProfile(
            framework=framework,
            framework_confidence=framework_confidence,
            model_id=model_id,
            detected_patterns=detected_patterns,
            reliability=reliability,
            wastefulness=wastefulness,
            security=security,
        )

    # ------------------------------------------------------------------
    # Private loaders
    # ------------------------------------------------------------------

    def _load_reliability(self) -> Optional[ReliabilityResult]:
        return self._read(
            _RELIABILITY_FILE,
            ReliabilityResult,
        )

    def _load_wastefulness(self) -> Optional[WastefulnessResult]:
        return self._read(
            _WASTEFULNESS_FILE,
            WastefulnessResult,
        )

    def _load_security(self) -> Optional[SecurityResult]:
        return self._read(
            _SECURITY_FILE,
            SecurityResult,
        )

    def _read(self, filename: str, model_cls):  # type: ignore[type-arg]
        path = self._dir / filename
        if not path.exists():
            if self._strict:
                raise CheckResultNotFound(
                    f"Check result not found: {path}. "
                    "Run the preceding check first."
                )
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return model_cls.model_validate(raw)


def _parse_patterns(raw: list[str]) -> list[DetectedPattern]:
    result: list[DetectedPattern] = []
    for s in raw:
        try:
            result.append(DetectedPattern(s))
        except ValueError:
            pass  # unknown pattern — skip silently
    return result
