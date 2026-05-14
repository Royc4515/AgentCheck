from utils import count_tokens

def generic_adapter(task_prompt, legacy_agent):
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
# בתוך ה-Adapter:
# tokens = count_tokens(response.text)