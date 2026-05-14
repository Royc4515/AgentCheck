"""Read/write helpers for the ``.agentcheck/`` results directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_results_dir(results_dir: Path) -> Path:
    """Create ``results_dir`` if missing and return it as an absolute path."""
    results_dir = results_dir.resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def write_json(path: Path, payload: Any) -> Path:
    """Serialise ``payload`` (dict or pydantic model) to JSON at ``path``."""
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    elif hasattr(payload, "dict"):
        data = payload.dict()
    else:
        data = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
