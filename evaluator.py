import json

class QualityEvaluator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def evaluate_metric(self, agent_output: str, metric_name: str, rubric: str) -> dict:
        prompt = f"""
        Evaluate this AI agent's output based ONLY on the following rubric.
        Rubric for {metric_name}: {rubric}
        
        Agent Output:
        '''{agent_output}'''
        
        Return ONLY valid JSON: {{"score": <0-100>, "reason": "<short>"}}
        """
        response_text = self.llm_client.generate(prompt)
        try:
            return json.loads(response_text)
        except:
            return {"score": 0, "reason": "Evaluation failed to parse"}

    def evaluate_all(self, agent_outputs: dict, metrics: list) -> dict:
        results = {}
        total_overall_score = 0
        
        for test_name, output in agent_outputs.items():
            test_score = 0
            metric_results = {}
            for metric in metrics:
                res = self.evaluate_metric(output, metric["metric_name"], metric["rubric"])
                metric_results[metric["metric_name"]] = res
                test_score += res.get("score", 0)
            
            avg_test_score = test_score / len(metrics) if metrics else 0
            results[test_name] = {"score": avg_test_score, "details": metric_results}
            total_overall_score += avg_test_score
            
        final_score = total_overall_score / len(agent_outputs) if agent_outputs else 0
        return {"final_score": final_score, "breakdown": results}