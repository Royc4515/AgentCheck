import json
from typing import Optional


class QualityEvaluator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def evaluate_metric(
        self,
        agent_output: str,
        metric_name: str,
        rubric: str,
        test_prompt: Optional[str] = None,
    ) -> dict:
        """Score a single agent output against one metric via one LLM call.

        Returns ``{"score": int, "reason": str}``. Any parsing or transport
        failure yields ``score=0`` with the reason describing why.
        """
        prompt_section = (
            f"\nOriginal Test Prompt:\n'''{test_prompt}'''\n" if test_prompt else ""
        )
        prompt = f"""You are a QA evaluator. Score the agent output below against the metric.
{prompt_section}
Agent Output:
'''{agent_output}'''

Metric: {metric_name}
Rubric: {rubric}

Return ONLY valid JSON of the form:
{{"score": <0-100>, "reason": "<short reason>"}}
"""
        response_text = self.llm_client.generate(prompt) or ""
        try:
            parsed = json.loads(response_text)
        except (json.JSONDecodeError, TypeError):
            return {"score": 0, "reason": "parse error"}

        if not isinstance(parsed, dict):
            return {"score": 0, "reason": "parse error"}

        score = parsed.get("score", 0)
        try:
            score = int(score)
        except (TypeError, ValueError):
            score = 0
        return {"score": score, "reason": parsed.get("reason", "")}

    def evaluate_all(
        self,
        agent_outputs: dict,
        metrics: list,
        test_prompts: Optional[dict] = None,
    ) -> dict:
        """Score every test output against every metric (one LLM call per pair).

        agent_outputs: {test_name: output_str}
        test_prompts:  {test_name: prompt_str}  — optional context per test
        """
        breakdown: dict = {}
        total_score = 0.0

        for test_name, output in agent_outputs.items():
            test_prompt = (test_prompts or {}).get(test_name)
            metric_details: dict = {}
            metric_sum = 0.0

            for m in metrics:
                name = m["metric_name"]
                rubric = m["rubric"]
                result = self.evaluate_metric(output, name, rubric, test_prompt=test_prompt)
                metric_details[name] = result
                metric_sum += result["score"]

            avg = metric_sum / len(metrics) if metrics else 0
            breakdown[test_name] = {"score": avg, "details": metric_details}
            total_score += avg

        final_score = total_score / len(agent_outputs) if agent_outputs else 0
        return {"final_score": final_score, "breakdown": breakdown}
