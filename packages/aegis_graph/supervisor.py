# packages/aegis_graph/supervisor.py
from __future__ import annotations
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langchain_core.messages import AIMessage, HumanMessage
from packages.aegis_graph.state import GraphState
from packages.core.llm_router import get_llm
from packages.core.prompts import get_prompt
from pydantic import BaseModel

class RouteDecision(BaseModel):
    next: Literal["researcher", "knowledge", "sre_analyst", "coder", "communicator", "evaluator", "finish"]
    reasoning: str

def supervisor_node(state: GraphState):
    task = state.get("task", "")
    iteration = state.get("iteration", 0)
    # Perception-Plan-Act-Reflect
    if iteration == 0 and not state.get("plan"):
        plan = ["sre_analyst", "knowledge", "coder", "evaluator", "communicator"]
        return {"plan": plan, "next_agent": plan[0]}
    # Router LLM with structured output
    llm = get_llm("reasoning")
    prompt = get_prompt("aegis/supervisor_router")
    artifacts_keys = ",".join(state.get("artifacts", {}).keys())
    try:
        router_llm = llm.with_structured_output(RouteDecision)
        decision = router_llm.invoke(prompt.format_messages(task=task, plan=state.get("plan", []), artifacts_keys=artifacts_keys or "none", iteration=iteration))
        next_agent = decision.next
    except Exception:
        # Fallback simple router
        plan = state.get("plan", [])
        confidence = state.get("confidence", 0)
        if confidence < 0.75 and "evaluator" not in artifacts_keys:
            next_agent = "evaluator"
        elif iteration < len(plan):
            next_agent = plan[iteration] if iteration < len(plan) else "finish"
        else:
            next_agent = "finish"
    # HITL Interrupt Loop
    if state.get("needs_human_approval"):
        payload = state.get("approval_payload") or {}
        user_input = interrupt({"approval_required": True, "payload": payload})
        # resume path
        if isinstance(user_input, dict) and user_input.get("approved") is False:
            return {"messages": [AIMessage(content="Human rejected action. Stopping.")], "next_agent": "finish"}
        # approved, clear flag
        return {"needs_human_approval": False, "approval_payload": None, "next_agent": next_agent}
    return {"next_agent": next_agent, "iteration": iteration + 1}

def route_after_supervisor(state: GraphState) -> str:
    n = state.get("next_agent", "finish")
    return n if n in {"researcher","knowledge","sre_analyst","coder","communicator","evaluator"} else "finish"

# Import subgraphs lazily to avoid circular import at module load in Vercel
def get_subgraph(name: str):
    if name == "researcher":
        from .subgraphs.researcher import researcher_agent; return researcher_agent
    if name == "knowledge":
        from .subgraphs.knowledge_agent import knowledge_agent; return knowledge_agent
    if name == "sre_analyst":
        from .subgraphs.sre_analyst import sre_agent; return sre_agent
    if name == "coder":
        from .subgraphs.coder import coder_agent; return coder_agent
    if name == "communicator":
        from .subgraphs.communicator import communicator_agent; return communicator_agent
    if name == "evaluator":
        from .subgraphs.evaluator import evaluator_agent; return evaluator_agent
    raise ValueError(name)

def run_subgraph_node(agent_name: str):
    def _node(state: GraphState):
        agent = get_subgraph(agent_name)
        result = agent.invoke(state)
        # merge
        return result
    return _node

# Build graph
graph_builder = StateGraph(GraphState)
graph_builder.add_node("supervisor", supervisor_node)
graph_builder.add_node("researcher", run_subgraph_node("researcher"))
graph_builder.add_node("knowledge", run_subgraph_node("knowledge"))
graph_builder.add_node("sre_analyst", run_subgraph_node("sre_analyst"))
graph_builder.add_node("coder", run_subgraph_node("coder"))
graph_builder.add_node("communicator", run_subgraph_node("communicator"))
graph_builder.add_node("evaluator", run_subgraph_node("evaluator"))

graph_builder.add_edge(START, "supervisor")
graph_builder.add_conditional_edges("supervisor", route_after_supervisor, {
    "researcher": "researcher",
    "knowledge": "knowledge",
    "sre_analyst": "sre_analyst",
    "coder": "coder",
    "communicator": "communicator",
    "evaluator": "evaluator",
    "finish": END,
})
for n in ["researcher","knowledge","sre_analyst","coder","communicator","evaluator"]:
    graph_builder.add_edge(n, "supervisor")

# Checkpointer
def get_checkpointer():
    import os
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if url and "postgres" in url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            return PostgresSaver.from_conn_string(url)
        except Exception:
            pass
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()

checkpointer = get_checkpointer()
graph = graph_builder.compile(checkpointer=checkpointer, name="aegis_supervisor")

# LCEL wrapper for LangServe
from langchain_core.runnables import RunnableLambda
def invoke_aegis(input_data: dict):
    task = input_data.get("input") or input_data.get("task") or ""
    config = {"configurable": {"thread_id": input_data.get("thread_id", "default")}}
    result = graph.invoke({"task": task, "messages": [HumanMessage(content=task)]}, config=config)
    return {"output": result["messages"][-1].content if result.get("messages") else "", "artifacts": result.get("artifacts", {}), "confidence": result.get("confidence", 0)}

aegis_runnable = RunnableLambda(invoke_aegis)
