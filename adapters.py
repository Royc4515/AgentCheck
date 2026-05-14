import tiktoken
def generic_adapter(task_prompt):
    # 1. הפעלת הסוכן האמיתי (נניח שהוא נקרא legacy_agent)
    response = legacy_agent.query(task_prompt)
    
    # 2. חילוץ הנתונים (נרחיב על זה בשלב הבא)
    return {
        "status": "success",
        "system_tokens": response.get('usage', {}).get('prompt_tokens', 0),
        "user_tokens": 0, 
        "completion_tokens": response.get('usage', {}).get('completion_tokens', 100),
        "tools_called": response.get('metadata', {}).get('tools', [])
    }
def estimate_tokens(text):
    encoding = tiktoken.get_encoding("cl100k_base") # המקודד של GPT-4
    return len(encoding.encode(text))

# בתוך ה-Adapter:
# tokens = estimate_tokens(response.text)