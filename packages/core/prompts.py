# packages/core/prompts.py
import os
from langchain_core.prompts import ChatPromptTemplate

_LOCAL_PROMPTS = {
    "aegis/supervisor_router": """You are AEGIS Supervisor.
Task: {task}
Plan so far: {plan}
Artifacts keys: {artifacts_keys}
Iteration: {iteration}

Route to ONE specialist:
- researcher: external web research needed
- knowledge: internal RAG / docs lookup
- sre_analyst: metrics, logs, incidents, runbooks
- coder: write code, fix bugs, create PRs
- communicator: summarize, send Slack/email
- evaluator: critique output

Respond with JSON: {{"next": "<agent>", "reasoning": "..."}}
""",
    "aegis/rag_grader": """Grade if retrieved docs are relevant to the question.
Question: {question}
Documents: {documents}
Respond JSON: {{"is_relevant": true/false, "score": 0.0-1.0}}
""",
    "aegis/critic": """You are Evaluator/Critic.
Task: {task}
Answer: {answer}
Score faithfulness, correctness 0-1. Respond JSON: {{"faithfulness": float, "correctness": float, "feedback": "...", "pass": bool}}
""",
    "aegis/sre_analyst": "You are SRE Analyst. Analyze metrics, logs. Produce RCA. Task: {task}",
    "aegis/coder": "You are Coder agent. Write safe patches. Task: {task}",
    "aegis/researcher": "You are Researcher. Find 3 quality sources. Task: {task}",
    "aegis/communicator": "You are Communicator. Summarize clearly for humans. Task: {task}",
}

def pull_prompt(name: str, fallback: str | None = None) -> ChatPromptTemplate:
    """Prompt Hub with local fallback - LangSmith if keys present"""
    if os.getenv("LANGCHAIN_API_KEY"):
        try:
            from langsmith import Client
            client = Client()
            prompt = client.pull_prompt(name)
            return prompt  # type: ignore
        except Exception:
            pass
    text = _LOCAL_PROMPTS.get(name, fallback or "You are a helpful assistant. {input}")
    return ChatPromptTemplate.from_template(text)

def get_prompt(name: str) -> ChatPromptTemplate:
    return pull_prompt(name)
