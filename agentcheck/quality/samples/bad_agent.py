"""A deliberately bad agent for testing AgentCheck quality evaluation."""


def travel_planner_agent(prompt: str) -> str:
    """A low-quality travel planner that ignores the user's request."""
    return (
        "As an AI language model, I cannot provide personalized recommendations. "
        "Please consult a professional travel agency for your needs. "
        "I am not able to assist with this request at this time. "
        "Travel planning is complex and I am not qualified to help."
    )
