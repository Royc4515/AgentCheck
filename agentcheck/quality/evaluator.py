import json


class QualityEvaluator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def evaluate_all(
        self, agent_outputs: dict, metrics: list, test_prompts: dict | None = None
    ) -> dict:
        """Score every test output against every metric.

        Batches all metrics into a single LLM call per test to stay within
        Groq rate limits (1 call per test instead of 1 per metric per test).

        agent_outputs: {test_name: output_str}
        test_prompts:  {test_name: prompt_str}  — optional; enables context-aware scoring
        """
        results = {}
        total_overall_score = 0

        metrics_block = "\n".join(
            f'  "{m["metric_name"]}": "{m["rubric"]}"'
            for m in metrics
        )
        metric_names = [m["metric_name"] for m in metrics]

        for test_name, output in agent_outputs.items():
            prompt_ctx = (test_prompts or {}).get(test_name, "")
            prompt_context_line = (
                f"\nOriginal Test Prompt:\n'''{prompt_ctx}'''\n" if prompt_ctx else ""
            )

            prompt = f"""
You are a QA evaluator. Score the agent output below against EACH metric.
{prompt_context_line}
Agent Output:
'''{output}'''

Metrics and rubrics:
{{
{metrics_block}
}}

Return ONLY valid JSON with a score (0-100) and short reason for each metric:
{{
{chr(10).join(f'  "{name}": {{"score": <0-100>, "reason": "<short>"}}' for name in metric_names)}
}}
"""
            response_text = self.llm_client.generate(prompt)
            try:
                parsed = json.loads(response_text)
            except Exception:
                parsed = {}

            metric_results = {}
            test_score = 0
            for name in metric_names:
                entry = parsed.get(name, {})
                if not isinstance(entry, dict):
                    entry = {}
                score = entry.get("score", 0)
                metric_results[name] = {
                    "score": score,
                    "reason": entry.get("reason", "parse error"),
                }
                test_score += score

            avg_test_score = test_score / len(metrics) if metrics else 0
            results[test_name] = {"score": avg_test_score, "details": metric_results}
            total_overall_score += avg_test_score

        final_score = total_overall_score / len(agent_outputs) if agent_outputs else 0
        return {"final_score": final_score, "breakdown": results}
