# packages/aegis_graph/subgraphs/communicator.py
from langgraph.graph import StateGraph, START, END
from packages.aegis_graph.state import GraphState
from packages.core.llm_router import get_llm
from packages.core.prompts import get_prompt
from langchain_core.messages import AIMessage

def communicate_node(state: GraphState):
    task = state.get("task","")
    artifacts = state.get("artifacts", {})
    llm = get_llm("fast")
    prompt = get_prompt("aegis/communicator")
    try:
        resp = (prompt | llm).invoke({"task": f"Summarize for incident channel. Task: {task}\nArtifacts: {list(artifacts.keys())}"})
        text = getattr(resp, "content", str(resp))
    except Exception:
        text = f"AEGIS Summary: Task '{task}' completed with confidence {state.get('confidence',0):.2f}. Artifacts: {', '.join(artifacts.keys())}"
    return {"messages": [AIMessage(content=text)], "confidence": state.get("confidence", 0.8), "needs_human_approval": True,
            "approval_payload": {"type": "slack_post", "channel": "#incidents", "message": text}}

graph = StateGraph(GraphState)
graph.add_node("communicate", communicate_node)
graph.add_edge(START, "communicate")
graph.add_edge("communicate", END)
communicator_agent = graph.compile()
