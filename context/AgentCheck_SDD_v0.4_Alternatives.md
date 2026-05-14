
AgentCheck: Check #4 — Does a Better Agent Exist?

Software Design Document (SDD) v0.4 May 2026   

1. Overview
Check #4 evaluates whether a superior solution to the developer's current agent exists. Unlike previous checks that measure absolute properties, this module provides an opinionated landscape analysis to ensure developers aren't stuck using outdated frameworks or inefficient patterns.  
+2

1.1 Goals

Concrete Recommendations: Provide evidence-backed alternatives.  


Quantified Trade-offs: Compare alternatives based on cost, reliability, and complexity.  


Maintain Freshness: Regularly update the knowledge base to prevent recommendation rot.  

1.2 Non-Goals

No Auto-Rewriting: The tool suggests, but does not execute, code changes.  


No Popularity Contests: Recommendations are based on fit, not GitHub stars.  

2. Defining "Better"
An alternative must dominate on at least one axis (improving by a specific percentage) and not regress more than 15% on any other metric to be recommended.  

Axis	Metric	"Better" Threshold
Reliability	Check #1 Completion Rate	
Passes 
≥10%
 more tasks.

Cost	Check #2 Cost per Task	

≥30%
 lower cost.

Security	Check #3 Finding Count	
Avoids same vulnerabilities by design.

Code Complexity	LOC / Cyclomatic Complexity	

≥40%
 less code required.

Maintenance	Project Health Metrics	
Active maintenance vs. stagnant choice.

3. The Alternatives Knowledge Base (KB)
The KB is a versioned YAML directory containing snapshots of frameworks and patterns. It includes:  


Frameworks: LangChain, AutoGen, PydanticAI, etc.  


Patterns: ReAct loops vs. plan-and-execute.  


Architectural Shifts: Determining if an LLM is needed at all.  


The "Honesty Test": If a task can be solved with a deterministic function (like a regex), AgentCheck will recommend deleting the LLM entirely.  

4. Matching & Validation
AgentCheck uses the agent's metadata (framework, model, tools, LOC) to filter and rank candidates from the KB.  
+1

4.1 Empirical Validation (Expensive Mode)
For top-ranked candidates, users can opt-in to --validate-alternative.  


Auto-Generate: Uses an LLM to write a minimal equivalent agent in the new framework.  


Re-Run Battery: Executes the task battery from Check #1 against the new agent.  


Compare: Directly measures if the alternative actually performs better.  

5. Implementation Roadmap
Milestone	Deliverable	Dependency
M17	
KB v1.0 with 8 framework entries and evidence.

None
M18	
Matching Algorithm (Filter, Score, Rank).

M17, v0.1 M1, v0.2 M7
M20	
Empirical Validation Pipeline (Auto-rewrite + Re-run).

M18, v0.1 M3
M21	
Reporter Integration (3 output modes).

M18
6. Example Output: The "Delete the LLM" Case
Plaintext
$ agentcheck run ./agent.py --check alternatives

┌─────────────────────────────────────────────┐
│  RECOMMENDATION    Delete the LLM           │
└─────────────────────────────────────────────┘

Your agent extracts email addresses. This is a regex task.
You're spending $0.003/call on a $0 task. [cite: 557-560]

Suggested replacement:
import re
emails = re.findall(EMAIL_PATTERN, text) [cite: 562-563]

Estimated savings: 100% of current inference cost. [cite: 564]