"""AgentCheck — AI agent audit tool.

Pipeline (run in order):
  check #1  reliability  → writes .agentcheck/reliability_result.json
  check #2  wastefulness → writes .agentcheck/wastefulness_result.json
  check #3  security     → writes .agentcheck/security_result.json
  check #4  alternatives → reads all three, returns FullComparisonReport

Entry point for check #4::

    from agentcheck.alternatives import run
    report = run()          # reads .agentcheck/*.json, prints terminal report
    report = run(strict=True, output_mode="json")
"""
