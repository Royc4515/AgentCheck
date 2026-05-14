# agent_template.py (שמור את זה מראש!)
from agentcheck.efficiency.utils import count_tokens

def quick_adapter(user_prompt):
    # ==========================================
    # TODO 1: ייבוא והפעלת הסוכן החדש
    # ==========================================
    # from other_team_code import their_agent_function
    # raw_response = their_agent_function(user_prompt)
    raw_response = "Placeholder text from the new agent..." # למחוק אחר כך
    
    # ==========================================
    # TODO 2: חילוץ נתונים חכם (Auto-Extract)
    # ==========================================
    # ננסה קודם למשוך נתונים אמיתיים (אם זה OpenAI או פריימוורק מוכר)
    actual_prompt_tokens = 0
    actual_completion_tokens = 0
    tools = []
    
    if hasattr(raw_response, 'usage'): # אם יש אובייקט Usage
        actual_prompt_tokens = raw_response.usage.prompt_tokens
        actual_completion_tokens = raw_response.usage.completion_tokens
    else:
        # Fallback: הסוכן הוא קופסה שחורה - נשתמש ב-Tiktoken
        text_output = str(raw_response)
        actual_prompt_tokens = count_tokens(user_prompt)
        actual_completion_tokens = count_tokens(text_output)
    
    # ==========================================
    # 3. החזרת הפורמט הסטנדרטי של AgentCheck
    # ==========================================
    return {
        "status": "success",
        "system_tokens": actual_prompt_tokens, 
        "user_tokens": 0, # הקלט כבר מחושב ב-prompt
        "completion_tokens": actual_completion_tokens,
        "tools_called": tools 
    }