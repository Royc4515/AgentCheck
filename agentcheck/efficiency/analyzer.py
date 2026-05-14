import json
import yaml
from collections import Counter

from agentcheck.shared import OpenRouterClient
from agentcheck.shared.openrouter_client import OpenRouterError

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
        total_input_tokens += tokens.get("system", 0) + tokens.get("user", 0)
        total_output_tokens += tokens.get("assistant", 0)
        
    model_pricing = pricing_data["models"].get(model_name, pricing_data["models"]["gpt-4o"])
    
    input_cost = (total_input_tokens / 1_000_000) * model_pricing["input_per_1m"]
    output_cost = (total_output_tokens / 1_000_000) * model_pricing["output_per_1m"]
    
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
            penalty_points += (count - 1) * 10
            redundant_tools.append(f"{tool}")
            
    return penalty_points, redundant_tools

# ==========================================
# 3. Heuristic Baseline (Detects Prompt Bloat)
# ==========================================
def analyze_heuristic_baseline(log_data, total_actual_tokens):
    """Estimates minimum tokens needed vs actual usage (Old method)."""
    input_chars = log_data["task_input_size_chars"]
    baseline_tokens = (input_chars // 4) + 100
    is_bloated = total_actual_tokens > (baseline_tokens * 2)
    
    return baseline_tokens, is_bloated

# ==========================================
# 4. LLM-as-a-Judge Baseline (Smart Baseline)
# ==========================================
# ==========================================
# 4. Hybrid Baseline (Heuristic + LLM Judge)
# ==========================================
def analyze_llm_baseline(task_prompt, actual_tokens):
    """
    Combines the stable math heuristic with the smart LLM estimation
    to create a robust, balanced baseline.
    """
    # 1. קודם כל, מחשבים את הבסיס היוריסטי ה"טיפש" והיציב
    heuristic_tokens = (len(task_prompt) // 4) + 100
    
    # 2. עכשיו, שואלים את שופט ה-AI
    print("   [Judge] Asking AI and Math to estimate optimal token usage...")
    llm_tokens = heuristic_tokens # ברירת מחדל במקרה של קריסה
    
    system_prompt = """
    You are an expert AI token estimator. Look at the user's task.
    Estimate the MINIMUM number of tokens needed to complete this task perfectly.
    Return ONLY a JSON object with a single key 'estimated_tokens' and an integer value.
    """
    
    try:
        client = OpenRouterClient()
        if client.has_key:
            result = client.chat_json(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"The task is: '{task_prompt}'"},
                ],
                temperature=0.2,
                max_tokens=200,
            )
            llm_tokens = int(result.get("estimated_tokens", heuristic_tokens))
    except (OpenRouterError, ValueError, TypeError) as e:
        print(f"   [Judge Warning] API failed, relying solely on math: {e}")

    # 3. השילוב! עושים ממוצע בין המתמטיקה לבין מה שה-AI אמר
    combined_baseline = (heuristic_tokens + llm_tokens) // 2
    
    print(f"   [Judge] Math suggested {heuristic_tokens}, AI suggested {llm_tokens}.")
    print(f"   [Judge] Combined Final Baseline: {combined_baseline} tokens.")

    # בודקים אם הסוכן התנפח מעבר לפעמיים מהבסיס המשולב
    is_bloated = actual_tokens > (combined_baseline * 2)
    
    return combined_baseline, is_bloated