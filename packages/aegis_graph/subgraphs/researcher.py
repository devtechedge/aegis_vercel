# packages/aegis_graph/subgraphs/researcher.py
from langgraph.graph import StateGraph, START, END
from packages.aegis_graph.state import GraphState
from packages.tools.registry import tavily_search, arxiv_tool
from langchain_core.messages import AIMessage

def research_node(state: GraphState):
    task = state.get("task","")
    web = tavily_search.invoke({"query": task})
    arxiv = arxiv_tool.invoke({"query": task})
    briefing = f"## Research Briefing\n\n### Web\n{web}\n\n### Arxiv\n{arxiv}\n"
    artifacts = {**state.get("artifacts", {}), "briefing.md": briefing}
    return {"messages": [AIMessage(content=briefing[:1200])], "artifacts": artifacts, "confidence": 0.72}

graph = StateGraph(GraphState)
graph.add_node("research", research_node)
graph.add_edge(START, "research")
graph.add_edge("research", END)
researcher_agent = graph.compile()
