import json
import yaml
import sys
from sandbox_runner import run_sandbox

# Imports
from dummy_agents import wasteful_agent, efficient_agent 
from analyzer import estimate_cost, analyze_tool_calls, analyze_heuristic_baseline
from downgrade_tester import run_downgrade_test, get_cheaper_model, mock_judge_evaluation
from reporter import print_terminal_report

# ==========================================
# 1. AGENT REGISTRY
# ==========================================
AGENTS = {
    "wasteful": wasteful_agent,
    "efficient": efficient_agent,
    "generic_v1": efficient_agent # Just for testing the command
}

# ==========================================
# 2. MAIN ORCHESTRATOR
# ==========================================

def start_audit(agent_name, task_prompt, model="gpt-4o-mini"):
    if agent_name not in AGENTS:
        print(f"Error: Agent '{agent_name}' not found.")
        print(f"Available agents: {', '.join(AGENTS.keys())}")
        return

    agent_func = AGENTS[agent_name]
    print(f"🚀 Starting Audit for: [{agent_name}]...")
    
    run_sandbox(agent_func, task_prompt, model_name=model)
    
    try:
        with open("execution_log.json", "r") as f:
            log = json.load(f)
        with open("pricing.yaml", "r") as f:
            pricing = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return
        
    actual_cost, actual_tokens = estimate_cost(log, pricing)
    tool_penalty_pts, redundant_tools = analyze_tool_calls(log)
    baseline_tokens, is_bloated = analyze_heuristic_baseline(log, actual_tokens)
    
    mini_pricing = pricing["models"]["gpt-4o-mini"]
    # Baseline assumes 114 tokens input + 20 tokens output
    baseline_cost = ((baseline_tokens / 1_000_000) * mini_pricing["input_per_1m"]) + \
                    ((20 / 1_000_000) * mini_pricing["output_per_1m"])
    
    original_model = log["agent_metadata"]["model_used"]
    cheaper_model = get_cheaper_model(original_model)
    overspec_penalty = 0
    
    if cheaper_model:
        judge = mock_judge_evaluation()
        if judge["passed"]:
            orig_rate = pricing["models"][original_model]["input_per_1m"]
            cheap_rate = pricing["models"][cheaper_model]["input_per_1m"]
            overspec_penalty = (actual_tokens / 1_000_000) * (orig_rate - cheap_rate)

    final_metrics = {
        'actual_cost': actual_cost,
        'baseline_cost': baseline_cost,
        'actual_tokens': actual_tokens,
        'baseline_tokens': baseline_tokens,
        'actual_latency': log["execution_log"]["total_latency_seconds"],
        'baseline_latency': 1.5,
        'overspec_penalty': max(0, overspec_penalty),
        'original_model': original_model,
        'cheaper_model': cheaper_model,
        'bloat_penalty': actual_cost * 0.15 if is_bloated else 0,
        'tool_penalty': (tool_penalty_pts / 100) * 0.01,
        'redundant_tools': redundant_tools
    }
    
    print_terminal_report(final_metrics)

if __name__ == "__main__":
    agent_to_test = "wasteful" 
    if len(sys.argv) > 1:
        agent_to_test = sys.argv[1]
    
    query = "I need a summary of the latest 5 orders for customer #8821"
    start_audit(agent_to_test, query)