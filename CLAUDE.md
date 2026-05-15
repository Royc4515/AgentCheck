# AgentCheck — Development Notes

## LLM Provider
All LLM calls route through **Groq** (`https://api.groq.com/openai/v1/chat/completions`).
Default model: `llama-3.3-70b-versatile`.
Set `GROQ_API_KEY` in your environment before running.

## Pipeline Steps & Status

| Step | Module | Status |
|------|--------|--------|
| Part 1 — Quality | `agentcheck/quality/` | ✅ working (Groq) |
| Part 2 — Efficiency | `agentcheck/efficiency/` | ✅ working (Groq) |
| Part 3 — Security | `agentcheck/security/` | ✅ working (Groq) |
| Part 4 — Alternatives | `agentcheck/alternatives/` | ✅ working (Groq) |

## Key Files
- Shared LLM client: `agentcheck/shared/openrouter_client.py`
- Pricing table: `agentcheck/efficiency/pricing.yaml`
- Sample agents: `agentcheck/quality/samples/`
