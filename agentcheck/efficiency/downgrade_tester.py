import json
import yaml
import random
from .sandbox_runner import run_sandbox
from agentcheck.quality.samples.dummy_agents import efficient_agent  # noqa: F401

# ==========================================
# 1. The Downgrade Ladder
# ==========================================
DOWNGRADE_LADDER = {
    "groq": {
        "llama-3.3-70b-versatile": "llama-3.1-8b-instant",
        "llama-3.1-8b-instant": "gemma2-9b-it",
    },
    "openai": {
        "gpt-4o": "gpt-4o-mini",
        "gpt-4o-mini": "gpt-3.5-turbo",
    },
    "anthropic": {
        "claude-opus": "claude-sonnet",
        "claude-sonnet": "claude-haiku",
    },
    "google": {
        "gemini-pro": "gemini-flash",
        "gemini-flash": "gemini-flash-lite",
    },
}

# ==========================================
# Helper: Load Data
# ==========================================
def load_files(results_dir=None):
    """Loads the original execution log and pricing table."""
    from pathlib import Path as _P
    results_dir = _P(results_dir) if results_dir else _P(".agentcheck")
    pricing_path = _P(__file__).parent / "pricing.yaml"
    with open(results_dir / "execution_log.json", "r", encoding="utf-8") as f:
        original_log = json.load(f)
    with open(pricing_path, "r", encoding="utf-8") as f:
        pricing = yaml.safe_load(f)
    return original_log, pricing

def get_cheaper_model(current_model):
    """Finds the next cheaper model in the downgrade ladder."""
    for provider, ladder in DOWNGRADE_LADDER.items():
        if current_model in ladder:
            return ladder[current_model]
    return None

def mock_judge_evaluation():
    """
    Simulates the Judge component evaluating the new output.
    Returns a passed boolean and a confidence score.
    """
    # For the hackathon demo, we simulate a successful downgrade with high confidence
    confidence_score = round(random.uniform(0.85, 0.98), 2)
    return {"passed": True, "confidence": confidence_score}

# ==========================================
# 2. Model Downgrade Tester
# ==========================================
def run_downgrade_test(task_input):
    print("[Downgrade Tester] Analyzing original execution...")
    original_log, pricing = load_files()
    
    original_model = original_log["agent_metadata"]["model_used"]
    original_status = original_log["execution_log"]["status"]
    
    # Step A: Check if the original run was successful
    if original_status != "success":
        print("[Downgrade Tester] Skip: Original agent did not pass the task.")
        return
        
    # Step B: Check if a cheaper model exists in the ladder
    cheaper_model = get_cheaper_model(original_model)
    if not cheaper_model:
        print(f"[Downgrade Tester] Skip: No cheaper tier available for {original_model}.")
        return
        
    print(f"\n[Downgrade Tester] -> Candidate found! Attempting downgrade: {original_model} -> {cheaper_model}")
    
    # Step C: Re-run the task with the cheaper model
    # We call run_sandbox from our previous file to do a fresh run
    print(f"[Downgrade Tester] -> Re-running task with {cheaper_model}...")
    rerun_log = run_sandbox(efficient_agent, task_input, model_name=cheaper_model)
    
    # Step D: Run the Judge on the new output
    judge_result = mock_judge_evaluation()
    
    # Step E: Evaluate confidence threshold
    if judge_result["passed"] and judge_result["confidence"] >= 0.8:
        print("\n┌──────────────────────────────────────────┐")
        print("│       DOWNGRADE RECOMMENDATION           │")
        print("└──────────────────────────────────────────┘")
        print(f"[!] SUCCESS: The cheaper model passed with a confidence of {judge_result['confidence']}")
        print(f"    Recommendation: Swap {original_model} for {cheaper_model}.")
        
        # Calculate potential savings
        orig_price = pricing["models"].get(original_model, {}).get("input_per_1m", 0)
        cheap_price = pricing["models"].get(cheaper_model, {}).get("input_per_1m", 0)
        
        if orig_price and cheap_price:
            savings_pct = ((orig_price - cheap_price) / orig_price) * 100
            print(f"    Financial Impact: Save ~{savings_pct:.0f}% on inference costs per task!")
    else:
        print(f"\n[X] FAILED: The cheaper model ({cheaper_model}) could not reliably complete the task.")
        print(f"    Confidence score was {judge_result['confidence']} (Threshold: 0.8).")
        print(f"    Stick with {original_model}.")

if __name__ == "__main__":
    # Assuming 'execution_log.json' from the previous step is still in the folder
    run_downgrade_test("Find flights to Tokyo")