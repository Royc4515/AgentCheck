import math

# ==========================================
# 1. Score Calculation
# ==========================================
def calculate_waste_score(baseline_cost, actual_cost):
    """
    Calculates the 0-100 Wastefulness Score based on the SDD formula.
    0 = optimal, 100 = catastrophic.
    """
    if actual_cost <= 0 or baseline_cost >= actual_cost:
        return 0
    
    # SDD Formula: 100 - (baseline_cost / actual_cost) * 100
    score = 100 - (baseline_cost / actual_cost) * 100
    
    # Clamp the score between 0 and 100
    return max(0, min(100, int(score)))

# ==========================================
# 2. Terminal UI Generator
# ==========================================
def print_terminal_report(metrics):
    """
    Renders the cocky terminal output exactly as specified in the SDD mock.
    """
    score = calculate_waste_score(metrics['baseline_cost'], metrics['actual_cost'])
    
    # Terminal Header
    print("\nAgentCheck v0.2  —  let's see where your money's going")
    print("─────────────────────────────────────────────────────")
    
    # Score Box
    print("┌──────────────────────────────────────────┐")
    # Formatting score to always take 2 spaces for alignment
    print(f"│  WASTEFULNESS SCORE          {score:2d} / 100    │") 
    print("│  (lower is better; 0 = optimal)          │")
    print("└──────────────────────────────────────────┘")
    
    # Base Metrics
    print(f"Cost per task:    ${metrics['actual_cost']:.3f}  (baseline: ${metrics['baseline_cost']:.3f})")
    print(f"Tokens per task:  {metrics['actual_tokens']:,}   (baseline: {metrics['baseline_tokens']:,})")
    print(f"Latency per task: {metrics['actual_latency']}s    (baseline: {metrics['baseline_latency']}s)")
    
    # Waste Breakdown Section
    print("\nWhere you're burning money:")
    
    # Condition 1: Model Overspecification
    if metrics.get('overspec_penalty', 0) > 0:
        penalty = metrics['overspec_penalty']
        print(f"• Model over-spec     -${penalty:.3f}/task")
        print(f"  {metrics['original_model']} passed the task, but {metrics['cheaper_model']} also passed.")
        print("  Recommendation: downgrade. Save money on inference.")
    
    # Condition 2: Prompt Bloat
    if metrics.get('bloat_penalty', 0) > 0:
        penalty = metrics['bloat_penalty']
        print(f"• Prompt bloat        -${penalty:.3f}/task")
        print(f"  System prompt used {metrics['actual_tokens']} tokens; baseline required only {metrics['baseline_tokens']}.")
    
    # Condition 3: Tool-Call Churn
    if metrics.get('tool_penalty', 0) > 0:
        penalty = metrics['tool_penalty']
        print(f"• Tool-call churn     -${penalty:.3f}/task")
        print(f"  Redundant tool calls detected: {', '.join(metrics['redundant_tools'])}.")
    
    # Final Verdict
    print("\nVerdict:")
    if score == 0:
        print("  Impressive. It actually works efficiently. Ship it.")
    elif score < 50:
        print("  It's okay, but this agent costs more than it should. Needs minor optimization.")
    else:
        print("  This agent costs ~4x what it should.")
        print("  Fix the model first; the prompt second.")
    print("\n")

# ==========================================
# Main Execution (Mock Data for Demo)
# ==========================================
if __name__ == "__main__":
    # Simulating the exact metrics from the SDD mock for the terminal preview
    mock_metrics = {
        'actual_cost': 0.084,
        'baseline_cost': 0.022,
        'actual_tokens': 4200,
        'baseline_tokens': 1100,
        'actual_latency': 4.1,
        'baseline_latency': 1.8,
        
        # Breakdown penalties in dollars
        'overspec_penalty': 0.058,
        'original_model': 'GPT-4o',
        'cheaper_model': 'GPT-4o-mini',
        
        'bloat_penalty': 0.011,
        
        'tool_penalty': 0.004,
        'redundant_tools': ['lookup_order']
    }
    
    print_terminal_report(mock_metrics)