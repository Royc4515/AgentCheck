import time
from openai import OpenAI
from generator import DynamicTestGenerator
from evaluator import QualityEvaluator
from actual_agents import travel_planner_agent

class RealLLMClient:
    def __init__(self):
        # הדבק כאן את המפתח של Groq שקיבלת מהדיספליי (ה-GSK KEY)
        self.api_key = "..."
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1", 
            api_key=self.api_key
        )
        #llama-3.3-70b-versatile הוא מודל חזק מאוד וחינמי כרגע.
        self.model = "llama-3.3-70b-versatile" 

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise JSON-generating system. Return strictly valid JSON."}, 
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e: 
            return f'{{"error": "{str(e)}"}}'

def run_dummy_agent(prompt, agent_type, llm_client):
    personas = {
        "good": "You are a professional assistant. Answer directly and concisely.",
        "yapper": "You are a robotic AI. Start with 'As an AI language model', be extremely verbose.",
        "average": "Be very polite, but intentionally miss one small detail from the user's prompt."
    }
    response = llm_client.client.chat.completions.create(
        model=llm_client.model,
        messages=[
            {"role": "system", "content": personas.get(agent_type, "Helpful assistant.")}, 
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def run_agent_checker():
    """
    נקודת הכניסה הראשית למערכת. 
    אפשר לקרוא לה מקבצים אחרים (כמו ה-main של הצוות).
    """
    print("\n=====================================================")
    print(" AgentCheck v0.3 — Modular Mode (FirstPart) w/ Debug")
    print("=====================================================\n")
    
    llm_client = RealLLMClient()
    generator = DynamicTestGenerator(llm_client)
    evaluator = QualityEvaluator(llm_client)
    
    purpose = input("Enter Agent Purpose: ")
    mode = input("Test Dummy or Real agent? (dummy/real): ").lower()
    agent_choice = input("Which dummy? (good/yapper/average): ").lower() if mode == "dummy" else ""

    # שלב 1: ייצור המבחנים
    print("\n⚙️  Synthesizing 5 specialized test cases...")
    suite = generator.generate_suite(purpose)
    tests = suite.get("tests", [])
    metrics = suite.get("custom_metrics", [])
    
    if not tests:
        print("❌ Generation failed. Check API Key."); return

    outputs = {}
    print(f"🚀 Running {len(tests)} tests against the agent...")
    
    for i, t in enumerate(tests):
        name, pr = t['name'], t['prompt']
        print(f"\n   [{i+1}/5] Executing: {name}")
        
        # הרצה של המודלים
        if mode == "real":
            # קריאה לסוכן הנסיעות (תכף נשנה אותו לסוכן שלכם!)
            outputs[name] = travel_planner_agent(pr, llm_client.api_key)
        else:
            # קריאה לסוכני הדמה
            outputs[name] = run_dummy_agent(pr, agent_choice, llm_client)
            
        # =============================================================
        # 🟢 הוספה: דיבאג - הצגת התשובה המלאה של הסוכן על המסך
        # =============================================================
        print(f"   -> [RAW OUTPUT] From agent for '{name}':")
        print(f"      '''\n{outputs[name]}\n      '''")
        # =============================================================
            
    # שלב 2: שיפוט
    print("\n⚖️  Evaluating results with LLM-as-a-Judge...\n")
    results = evaluator.evaluate_all(outputs, metrics)
    
    # שלב 3: דוח סופי
    print("\n" + "═"*50)
    print(f" FINAL AGENT SCORE: {results['final_score']:03.0f} / 100")
    print("═"*50)
    
    for test, data in results["breakdown"].items():
        print(f"\n📌 {test} (Overall: {data['score']:.0f})")
        for m, m_data in data['details'].items():
            status = "✅" if m_data['score'] >= 80 else "⚠️"
            print(f"   {status} {m.ljust(25)}: {m_data['score']} pts -> {m_data['reason']}")

if __name__ == "__main__":
    # זה מאפשר להריץ את הקובץ ישירות כרגיל
    run_agent_checker()