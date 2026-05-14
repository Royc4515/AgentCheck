import time
import json

# Import the mock agents we created in Phase 1
from dummy_agents import wasteful_agent, efficient_agent

def run_sandbox(agent_func, task_input, model_name="gpt-4o"):
    """
    Executes an agent in an isolated manner, captures metrics (latency, tokens),
    and exports a structured JSON log.
    """
    print(f"[Runner] Starting isolated execution for model: {model_name}...")
    
    # 1. Start the timer (Crucial for the Latency Drag check later)
    start_time = time.time()
    
    # 2. Execute the target agent with the given task
    try:
        response = agent_func(task_input)
        status = response.get("status", "unknown")
    except Exception as e:
        response = {}
        status = "error"
        print(f"[Runner] Agent execution failed: {e}")
    
    # 3. Stop the timer and calculate total latency
    end_time = time.time()
    latency = round(end_time - start_time, 2)
    
    # 4. Construct the execution log precisely matching the SDD schema
    # This JSON structure is the contract between you and the other components (like Eliyahu's Judge)
    log = {
        "task_id": "test_001",
        "task_input_size_chars": len(task_input),
        "agent_metadata": {
            "model_used": model_name
        },
        "execution_log": {
            "total_latency_seconds": latency,
            "status": status,
            "steps": [
                {
                    "step_id": 1,
                    "type": "llm_call",
                    "latency_seconds": latency,
                    "tokens": {
                        "system": response.get("system_tokens", 0),
                        "user": response.get("user_tokens", 0),
                        "assistant": response.get("completion_tokens", 0),
                        "tool": 0
                    },
                    "tools_used": response.get("tools_called", [])
                }
            ]
        }
    }
    
    # 5. Write the structured data to a JSON file
    # Ensure encoding is utf-8 to handle any Hebrew/special characters in prompts
    output_filename = "execution_log.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=4)
        
    print(f"[Runner] Execution finished in {latency}s. Log saved to {output_filename}")
    return log

if __name__ == "__main__":
    # Test the runner with the wasteful agent
    print("--- Running Test 1: Wasteful Agent ---")
    run_sandbox(wasteful_agent, "Find flights to Tokyo")
    
    print("\n--- Running Test 2: Efficient Agent ---")
    run_sandbox(efficient_agent, "Find flights to Tokyo")