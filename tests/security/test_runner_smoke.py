"""Smoke test: run_security reads agent source from path, writes JSON contract."""

from pathlib import Path

from agentcheck.alternatives.models import SecurityResult
from agentcheck.security import run_security


_VULN_AGENT = '''
"""Intentionally insecure agent for testing."""

import pickle

API_KEY = "sk-abcdef0123456789ABCDEF0123456789"

def vulnerable_agent(user_input: str) -> str:
    data = pickle.loads(user_input.encode())
    return f"Got {data}"
'''


def test_run_security_writes_security_json_for_clean_agent(
    fixture_agent_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = run_security(fixture_agent_path, fixture_results_dir)
    assert isinstance(result, SecurityResult)

    out = fixture_results_dir / "security_result.json"
    assert out.exists()
    parsed = SecurityResult.model_validate_json(out.read_text())
    assert parsed.is_safe is True
    assert parsed.critical_count == 0
    assert parsed.high_count == 0


def test_run_security_detects_vulnerable_agent(
    tmp_path: Path, fixture_results_dir: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    bad = tmp_path / "bad_agent.py"
    bad.write_text(_VULN_AGENT, encoding="utf-8")

    result = run_security(bad.resolve(), fixture_results_dir)
    assert result.hardcoded_secrets is True
    assert result.unsafe_deserialization is True
    assert result.is_safe is False
    # Timestamped report should be written under reports/
    assert any((fixture_results_dir / "reports").glob("security_*.json"))
