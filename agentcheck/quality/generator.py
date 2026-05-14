import json

class DynamicTestGenerator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate_suite(self, agent_purpose: str) -> dict:
        prompt = f"""
        You are a Senior QA Automation Engineer.
        Agent Purpose: "{agent_purpose}"
        
        Generate a comprehensive test suite with 5 diverse test cases.
        Include different types: Happy Path, Complex Logic, Negative Test, and Instruction Following.

        Return strictly valid JSON in this format:
        {{
            "tests": [
                {{
                    "name": "Test Name",
                    "prompt": "The actual prompt",
                    "type": "happy_path/edge_case/logic"
                }}
            ],
            "custom_metrics": [
                {{
                    "metric_name": "Task Accuracy",
                    "rubric": "Score 100 if the agent perfectly completed the task. Score 0 if it failed or hallucinated."
                }},
                {{
                    "metric_name": "Conciseness",
                    "rubric": "Score 100 if short and to the point. Lower if it adds unnecessary fluff."
                }},
                {{
                    "metric_name": "AI-Likeness",
                    "rubric": "Score 100 if human-like. Score 20 if it uses cliches like 'As an AI' or sounds robotic."
                }},
                {{
                    "metric_name": "Tone and Politeness",
                    "rubric": "Score 100 if the tone is perfectly suited for the purpose (e.g., helpful, professional). Score lower if rude or inappropriate."
                }},
                {{
                    "metric_name": "Readability & Formatting",
                    "rubric": "Score 100 if the output is well-structured, easy to read, and uses proper spacing or bullets."
                }},
                {{
                    "metric_name": "Completeness",
                    "rubric": "Score 100 if the agent addressed ALL parts of the query and constraints. Score lower if it missed details."
                }}
            ]
        }}
        """
        response_text = self.llm_client.generate(prompt)
        try:
            parsed = json.loads(response_text)
            return {
                "tests": parsed.get("tests") or [],
                "custom_metrics": parsed.get("custom_metrics") or [],
            }
        except Exception as e:
            print(f"❌ Error parsing test suite: {e}")
            return {"tests": [], "custom_metrics": []}