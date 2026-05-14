# dummy_agents.py
import time
from utils import count_tokens

def universal_adapter(task_prompt):
    # 1. הרצת הסוכן הגנרי (שמייצג כל סוכן שתקבל)
    # נניח שזה סוכן שמחזיר רק string פשוט
    raw_response = "Here is the summary of the orders..." 
    
    # 2. שימוש ב-tiktoken כדי לשערך את העלות
    # אנחנו סופרים את הפרומפט (קלט) ואת התגובה (פלט)
    in_tokens = count_tokens(task_prompt)
    out_tokens = count_tokens(raw_response)
    
    # 3. החזרת הפורמט ש-AgentCheck אוהב
    return {
        "status": "success",
        "system_tokens": 100, # הערכה קבועה למערכת אם אין גישה
        "user_tokens": in_tokens,
        "completion_tokens": out_tokens,
        "tools_called": [] # אם אין לנו גישה ללוג הכלים
    }

def efficient_agent(task_prompt):
    # Super-slim agent for the "Perfect 0" demo
    return {
        "status": "success",
        "system_tokens": 80,   # Very small system prompt
        "user_tokens": 20,     # Small input
        "completion_tokens": 10, # Minimal output
        "tools_called": []     # No tools
    }

def wasteful_agent(task_prompt):
    # Simulate an inefficient agent that burns tokens and time
    time.sleep(2.5) 
    estimated_user_tokens = len(task_prompt) // 4
    return {
        "status": "success",
        "system_tokens": 1500,
        "user_tokens": estimated_user_tokens,
        "completion_tokens": 400,
        "tools_called": ["search_web", "search_web"]
    }