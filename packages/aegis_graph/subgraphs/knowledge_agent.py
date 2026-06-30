# packages/aegis_graph/subgraphs/knowledge_agent.py
from langgraph.graph import StateGraph, START, END
from packages.aegis_graph.state import GraphState
from packages.rag.retriever import rag_self_correct
from packages.core.llm_router import get_llm
from packages.core.prompts import get_prompt
from langchain_core.messages import AIMessage

def rag_node(state: GraphState):
    task = state.get("task", "")
    docs, iterations = rag_self_correct(task)
    answer_prompt = get_prompt("aegis/communicator")
    llm = get_llm("fast")
    try:
        answer = (answer_prompt | llm).invoke({"task": f"{task}\n\nContext:\n" + "\n".join(docs)})
        text = getattr(answer, "content", str(answer))
    except Exception:
        text = f"RAG Answer (with {iterations} retrieval iterations):\n" + "\n".join(docs[:2])
    artifacts = state.get("artifacts", {}).copy()
    artifacts["knowledge_citations"] = docs
    artifacts["rag_iterations"] = iterations
    return {"messages": [AIMessage(content=text)], "artifacts": artifacts, "confidence": 0.78}

graph = StateGraph(GraphState)
graph.add_node("rag", rag_node)
graph.add_edge(START, "rag")
graph.add_edge("rag", END)
knowledge_agent = graph.compile()
