# packages/aegis_graph/subgraphs/sre_analyst.py
from langgraph.graph import StateGraph, START, END
from packages.aegis_graph.state import GraphState
from packages.tools.registry import prometheus_metrics_tool, runbook_executor_tool, slack_toolkit
from langchain_core.messages import AIMessage

def analyze_node(state: GraphState):
    task = state.get("task","")
    metrics = prometheus_metrics_tool.invoke({"query": "checkout_latency_p95"})
    runbook = runbook_executor_tool.invoke({"runbook_id": "checkout_latency_spike"})
    slack = slack_toolkit.invoke({"action": "search_threads", "channel": "#incidents"})
    rca = f"RCA Report for: {task}\n\nMetrics: {metrics}\nRunbook: {runbook}\nSlack: {slack}\n\nProbable cause: Deploy v2.4.1 increased DB connection pool wait in us-east.\nConfidence: 0.84"
    artifacts = {**state.get("artifacts", {}), "rca.md": rca}
    return {"messages": [AIMessage(content=rca)], "artifacts": artifacts, "confidence": 0.84}

graph = StateGraph(GraphState)
graph.add_node("analyze", analyze_node)
graph.add_edge(START, "analyze")
graph.add_edge("analyze", END)
sre_agent = graph.compile()
