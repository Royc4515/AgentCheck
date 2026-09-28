# AgentCheck - Development Notes

## What this is
A local CLI for developers of Python AI agents that audits a single agent `.py` file on quality, efficiency (token cost) and security, then grades it A-F and names cheaper or better real-world alternatives (frameworks, patterns, or dropping the LLM).

## Stack & layout
Python >=3.10, pydantic v2, pyyaml, requests, tiktoken, python-dotenv, pytest. Entry point `agentcheck = agentcheck.cli:main`.
- `agentcheck/cli.py` - argparse CLI (`agentcheck run`), loads `.env`, validates the agent path.
- `agentcheck/orchestrator.py` - runs Parts 1 -> 2 -> 3 -> 4; a failing part logs and does not abort the rest.
- `agentcheck/shared/openrouter_client.py` - the single LLM client (name is legacy; see LLM provider).
- `agentcheck/quality/` - Part 1: LLM-generated test battery + LLM judge -> `reliability_result.json`.
- `agentcheck/efficiency/` - Part 2: runs the agent, counts tokens, prices via `pricing.yaml` -> `wastefulness_result.json`.
- `agentcheck/security/` - Part 3: regex static audit (`attack_library.yaml`) + LLM necessity classification -> `security_result.json`.
- `agentcheck/alternatives/` - Part 4: reads the three JSONs, scores A-F, matches the YAML KB in `alternatives/kb/` -> `final_report.json`.
- `scripts/refresh_kb.py` - refreshes KB YAMLs from GitHub + OpenRouter pricing (optional `GITHUB_TOKEN`).
- `context/` - design docs (SDD v0.1-v0.4), one per part.
- `tests/` - pytest suite mirroring the package; `tests/conftest.py` provides a toy agent fixture.

## Pipeline steps & status

| Step | Module | Status |
|------|--------|--------|
| Part 1 - Quality | `agentcheck/quality/` | working |
| Part 2 - Efficiency | `agentcheck/efficiency/` | working |
| Part 3 - Security | `agentcheck/security/` | working |
| Part 4 - Alternatives | `agentcheck/alternatives/` | working |

## LLM provider
All LLM calls go through `OpenRouterClient` in `agentcheck/shared/openrouter_client.py`. Provider order (first key found wins):
1. `GEMINI_API_KEY` -> Gemini OpenAI-compatible endpoint, model `gemini-2.0-flash`.
2. `GROQ_API_KEY` (or legacy `OPENROUTER_API_KEY`) -> Groq, model `llama-3.3-70b-versatile`.
3. `LOCAL_LLM_URL` / `LOCAL_LLM_MODEL` -> local Ollama / Podman, also used as fallback when the primary fails or rate-limits.

Part 4's verdict (`agentcheck/alternatives/verdict.py`) has its own order: `GEMINI_API_KEY_4` -> `GROQ_API_KEY` -> `OPENROUTER_API_KEY`. `GEMINI_API_KEY_4` is deliberately separate so Part 4 has its own quota.
Copy `.env.example` to `.env` and fill in keys; `.env` is git-ignored.

## Commands
- Install: `pip install -r requirements.txt` (verified), plus `pip install rich` (see Gotchas). `pip install -e ".[dev]"` is defined but unverified.
- Test: `python -m pytest -q` (verified: 137 passed with `rich` installed; no API keys or network needed).
- Full audit: `agentcheck run ./my_agent.py --task "..." --agent-description "..."` (unverified, needs an LLM key).
- Partial runs: `--skip security`, `--only alternatives`. `agentcheck run` with no path runs Part 4 only, from cached JSONs in `--results-dir` (default `./.agentcheck`).
- Refresh KB: `python scripts/refresh_kb.py` (unverified, needs network).

## Conventions (Roy's standing rules)
- Comments explain WHY, not what.
- Flag counterintuitive, load-bearing or past-bug-hiding lines with a `# don't touch / <reason>` comment.
- Edge cases and input validation are priorities (see `_validate_agent_path` in `cli.py`); prefer clean OOP, good naming, reuse.
- No em dashes in any user-facing text or docs (CLI output, reports, README, this file); use a plain hyphen.
- Secrets only via environment variables, never committed. `.env`, `.agentcheck/`, `reports/`, `execution_log.json` stay git-ignored.

## Key files
- Shared LLM client: `agentcheck/shared/openrouter_client.py`
- Pricing table: `agentcheck/efficiency/pricing.yaml`
- Static security signatures: `agentcheck/security/attack_library.yaml`
- Alternatives KB: `agentcheck/alternatives/kb/{frameworks,patterns,architectural}/*.yaml`
- Sample agents: `agentcheck/quality/samples/`

## Gotchas
- `rich` is imported by `agentcheck/alternatives/reporter.py` but missing from `requirements.txt` and `pyproject.toml`. Without it the reporter silently falls back to summary mode, skips the verdict, and `tests/alternatives/test_verdict.py::TestReporterWithVerdict::test_verdict_panel_rendered_when_text_returned` fails.
- The agent under test is imported and executed in-process via `importlib` (`quality/runner.py`, `efficiency/sandbox_runner.py`). No timeout or isolation yet, despite the SDD's "sandbox" wording; a hanging or side-effecting agent affects the audit itself.
- The agent entry point is guessed: first public function whose name contains "agent", else the first public function. Name the target function accordingly.
- `efficiency/sandbox_runner.py::_normalise_response` assumes `system_tokens=100` when the agent does not return its own token counts, so cost numbers for plain-string agents are estimates.
- `OpenRouterClient` / `OpenRouterError` names are historical; do not assume OpenRouter is called. `tests/shared/test_openrouter_client.py` pins the provider order.
- On a 429 the client fails fast to the local LLM if `LOCAL_LLM_URL` is set; otherwise it retries with 5/15/30s back-off, so runs without a local fallback can stall.
- `LOCAL_LLM_URL` port differs between `.env.example` (10434) and the client comment (11434 for Ollama); use whatever your local server listens on.
- `context/*.md` SDDs are partial exports (v0.1 starts mid-section 3.3 and ends with stray Python). Treat them as intent; the code is the source of truth.
- `README.md` is a one-line placeholder.
