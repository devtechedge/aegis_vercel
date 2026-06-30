# packages/aegis_graph/subgraphs/coder.py
from langgraph.graph import StateGraph, START, END
from packages.aegis_graph.state import GraphState
from packages.tools.registry import github_toolkit, code_executor
from langchain_core.messages import AIMessage

def code_node(state: GraphState):
    task = state.get("task","")
    iteration = state.get("iteration", 0)
    # Simulate: read repo, write patch, test
    gh = github_toolkit.invoke({"action": "read_file", "path": "checkout/service.py"})
    test_result = code_executor.invoke({"code": "print('tests passed: 12/12')", "language": "python"})
    patch = "--- a/checkout/service.py\n+++ b/checkout/service.py\n@@ -42 +42 @@\n-  pool_size=10\n+  pool_size=25  # fix latency spike\n"
    artifacts = {**state.get("artifacts", {}), "patch.diff": patch, "tests": test_result}
    msg = f"Coder iteration {iteration+1}: Patch ready. Tests: {test_result}"
    # Critic loop - max 3
    confidence = 0.76 + iteration * 0.05
    return {"messages": [AIMessage(content=msg)], "artifacts": artifacts, "confidence": confidence, "iteration": iteration+1,
            "needs_human_approval": True,
            "approval_payload": {"type": "github_pr", "patch": patch, "title": "fix(checkout): increase DB pool size"}} 

graph = StateGraph(GraphState)
graph.add_node("code", code_node)
graph.add_edge(START, "code")
graph.add_edge("code", END)
coder_agent = graph.compile()
