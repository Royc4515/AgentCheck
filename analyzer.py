import json
import yaml
from collections import Counter

# ==========================================
# 1. Cost Estimator
# ==========================================
def estimate_cost(log_data, pricing_data):
    """Calculates the dollar cost of the task based on tokens."""
    model_name = log_data["agent_metadata"]["model_used"]
    steps = log_data["execution_log"]["steps"]
    
    total_input_tokens = 0
    total_output_tokens = 0
    
    for step in steps:
        tokens = step.get("tokens", {})
        # System + User = Input tokens 
        total_input_tokens += tokens.get("system", 0) + tokens.get("user", 0)
        # Assistant = Output tokens 
        total_output_tokens += tokens.get("assistant", 0)
        
    # Get rates from pricing.yaml [cite: 67-77]
    model_pricing = pricing_data["models"].get(model_name, pricing_data["models"]["gpt-4o"])
    
    input_cost = (total_input_tokens / 1_000_000) * model_pricing["input_per_1m"]
    output_cost = (total_output_tokens / 1_000_000) * model_pricing["output_per_1m"]
    
    # Returns: (total_cost, total_tokens)
    return input_cost + output_cost, total_input_tokens + total_output_tokens

# ==========================================
# 2. Tool-Call Analyzer (Detects Tool-Call Churn)
# ==========================================
def analyze_tool_calls(log_data):
    """Scans for redundant tool invocations."""
    tools_used = log_data["execution_log"]["steps"][0].get("tools_used", [])
    tool_counts = Counter(tools_used)
    
    penalty_points = 0
    redundant_tools = []
    
    for tool, count in tool_counts.items():
        if count > 1:
            # Penalty for redundant calls 
            penalty_points += (count - 1) * 10
            redundant_tools.append(f"{tool}")
            
    return penalty_points, redundant_tools

# ==========================================
# 3. Heuristic Baseline (Detects Prompt Bloat)
# ==========================================
def analyze_heuristic_baseline(log_data, total_actual_tokens):
    """Estimates minimum tokens needed vs actual usage."""
    input_chars = log_data["task_input_size_chars"]
    # Formula based on SDD Section 2.2 
    baseline_tokens = (input_chars // 4) + 100
    is_bloated = total_actual_tokens > (baseline_tokens * 2)
    
    return baseline_tokens, is_bloated