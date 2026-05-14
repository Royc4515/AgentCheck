# agent_registry.py
from dummy_agents import wasteful_agent, efficient_agent
# כאן תוכל לייבא סוכנים מ-50 קבצים שונים

AGENTS = {
    "wasteful": wasteful_agent,
    "efficient": efficient_agent,
    # "insurance": insurance_agent_wrapper,
    # "billing": billing_agent_wrapper,
}

def get_agent(name):
    return AGENTS.get(name)

def list_agents():
    return list(AGENTS.keys())