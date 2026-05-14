from openai import OpenAI

def travel_planner_agent(prompt, api_key):
    # כאן הגדרת ש-client הוא האובייקט של OpenAI
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key
    )
    
    system_message = """
    You are a professional travel planner. 
    Your goal is to provide short, structured itineraries. 
    Always include exactly 3 attractions and 1 local food tip.
    """
    
    # כאן התיקון: מורידים .client אחד
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content