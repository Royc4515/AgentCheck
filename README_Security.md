🛡️ Agent-Auditor: Security Risk Evaluator
📌 Project Overview
The Agent-Auditor is a specialized security tool designed to analyze the source code of other AI agents. It identifies "Action-Data Mismatches," hidden information leaks, and over-privileged tool access.

Instead of just checking for syntax errors, this auditor uses a Static Analysis Engine combined with an LLM-based Reasoning Agent to determine if a group of files creates a dangerous vulnerability chain.

🏗️ Directory Structure
Plaintext 
agent-auditor/
├── .env                # Private API keys (Excluded from version control)
├── AGENTS.md           # The "SOP" - High-level instructions for the auditor
├── auditor.py          # The Brain - Orchestrates the scan and calls the LLM
├── src/                # The Muscles - Core Python logic
│   ├── scanner.py      # Performs AST parsing and regex secret hunting
│   ├── reporter.py     # Aggregates findings into Markdown/JSON reports
│   └── utils.py        # File system helpers and directory crawlers
├── rules/              # The Law - Policy files defining "What is Risky"
│   ├── leaks.yaml      # Patterns for secrets (.env, .pem, API tokens)
│   ├── sinks.yaml      # Dangerous functions (os.system, eval, subprocess)
│   └── logic.yaml      # Definitions of cross-file risk chains
├── reports/            # Output - Final security audit results
└── target_agents/      # The Suspects - The agent code being evaluated
    ├── chatbot_v1/     # Sample agent directory
    └── task_manager/   # Sample agent directory
🚀 How it Works
1. Extraction (Scanner)
The scanner.py script walks through the target_agents/ directory. It uses Python's Abstract Syntax Tree (AST) to map out every function call, every import, and every variable that looks like a secret.

2. Policy Application (Rules)
The system reads the .yaml files in the rules/ folder. These act as a "Checklist." The auditor won't just guess what is wrong; it will verify the code against these specific security standards.

3. Agentic Reasoning (The Brain)
The code "abstracts" are sent to the LLM (Gemini/Claude/GPT). The auditor asks:

Individually: Does this file have a backdoor or a hardcoded key?

Collectively: If File A reads a secret, can it pass that secret to a tool in File B that sends it to the internet?

4. Reporting
The reporter.py script generates a final Risk Factor Score (1-10) and a detailed breakdown of vulnerabilities, saved in the reports/ folder for your review.

🛑 Security Warning
Isolation: The code in target_agents/ is treated as untrusted.

Static Only: This version of the auditor reads the code but does not execute it, preventing any malicious agents from "attacking" your host machine during the audit.