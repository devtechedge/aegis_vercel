# packages/tools/registry.py
import os
from typing import Any
from langchain_core.tools import tool

@tool
def tavily_search(query: str) -> str:
    """Search the web with Tavily."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return f"[tavily mock] Results for '{query}': 3 relevant sources found (set TAVILY_API_KEY for live)."
    try:
        from langchain_tavily import TavilySearch
        t = TavilySearch(max_results=3)
        r = t.invoke(query)
        return str(r)[:2000]
    except Exception as e:
        return f"Tavily error (mock fallback): {e}"

@tool
def code_executor(code: str, language: str = "python") -> str:
    """Execute code in a sandbox. Read-only safe."""
    if language != "python":
        return "Only python supported in lite mode."
    # Very restricted exec for Vercel
    try:
        import io, contextlib
        buf = io.StringIO()
        safe_globals = {"__builtins__": {"print": print, "range": range, "len": len, "sum": sum}}
        with contextlib.redirect_stdout(buf):
            exec(code, safe_globals, {})
        return buf.getvalue()[:2000] or "Executed with no output."
    except Exception as e:
        return f"CodeExecutor error: {e}"

@tool
def postgres_sql_toolkit(query: str) -> str:
    """Read-only SQL against Postgres. Write operations require HITL."""
    if any(w in query.lower() for w in ["insert ", "update ", "delete ", "drop ", "alter "]):
        return "WRITE_BLOCKED: SQL write operations require human approval via HITL."
    # Mock for Vercel - real impl uses langchain-community SQLDatabase
    return f"[SQL mock] Would execute (read-only): {query[:200]} — 12 rows returned."

@tool
def github_toolkit(action: str, repo: str = "devtechedge/aegis_vercel", path: str = "") -> str:
    """GitHub: list_prs, read_file, create_pr_branch - PR creation HITL gated."""
    if "create_pr" in action or "branch" in action:
        return "HITL_REQUIRED: PR creation needs human approval. Payload stored."
    return f"[GitHub mock] action={action}, repo={repo}, path={path} — OK."

@tool
def slack_toolkit(action: str, channel: str = "#incidents", message: str = "") -> str:
    """Slack: search_threads, post_message — post is HITL gated."""
    if action == "post_message":
        return "HITL_REQUIRED: Slack send needs approval."
    return f"[Slack mock] Found 2 related threads in {channel} about recent deploy."

@tool
def browser_tool(url: str) -> str:
    """Playwright async scrape - lite mock."""
    return f"[Browser mock] Scraped {url} — title extracted, 850 chars."

@tool
def prometheus_metrics_tool(query: str) -> str:
    """Query Prometheus metrics - fake metrics API."""
    return f"[Prometheus mock] query='{query}' → p95_checkout_latency=420ms (spike +180%), error_rate=0.4%, us-east-1"

@tool
def runbook_executor_tool(runbook_id: str) -> str:
    """Execute YAML runbooks."""
    return f"[Runbook mock] Executed {runbook_id}: restart_cache → clear_queues → OK. Latency improved 15%."

@tool
def arxiv_tool(query: str) -> str:
    """Arxiv search."""
    try:
        from langchain_community.tools import ArxivQueryRun
        from langchain_community.utilities import ArxivAPIWrapper
        return ArxivQueryRun(api_wrapper=ArxivAPIWrapper(top_k_results=2)).run(query)[:1500]
    except Exception:
        return f"[Arxiv mock] 2 papers for '{query}'."

@tool
def wikipedia_tool(query: str) -> str:
    """Wikipedia search."""
    try:
        from langchain_community.tools import WikipediaQueryRun
        from langchain_community.utilities import WikipediaAPIWrapper
        return WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=1)).run(query)[:1500]
    except Exception:
        return f"[Wikipedia mock] Summary for '{query}'."

@tool
def send_email_tool(to: str, subject: str, body: str) -> str:
    """Send email — ALWAYS HITL gated."""
    return "HITL_REQUIRED: Email send needs human approval."

@tool
def calendar_tool(action: str = "list") -> str:
    """Calendar lookup."""
    return "[Calendar mock] No incidents scheduled. Next oncall: sre-team."

@tool
def file_system_tool(path: str, action: str = "read") -> str:
    """Sandboxed file system."""
    if ".." in path or path.startswith("/etc"):
        return "SECURITY_BLOCKED"
    return f"[FS mock] {action} {path} — OK, 1.2KB"

@tool
def memory_search_tool(query: str) -> str:
    """Long-term semantic memory PGVector search."""
    # real impl in packages/memory/
    return f"[Memory mock] Found 2 facts for '{query}': incident-342 (checkout), deploy v2.4.1"

# RAG retriever tool - lazy import to avoid circular
def get_vectorstore_retriever_tool():
    @tool
    def vectorstore_retriever_tool(query: str) -> str:
        """RAG vector store retriever."""
        try:
            from packages.rag.retriever import hybrid_retrieve
            docs = hybrid_retrieve(query)
            return "\n\n".join([d[:400] for d in docs[:3]]) or "No docs."
        except Exception as e:
            return f"[RAG mock] docs for '{query}' — fallback. Err: {e}"
    return vectorstore_retriever_tool

ALL_TOOLS = [
    tavily_search, code_executor, postgres_sql_toolkit, github_toolkit,
    slack_toolkit, browser_tool, prometheus_metrics_tool, runbook_executor_tool,
    arxiv_tool, wikipedia_tool, send_email_tool, calendar_tool, file_system_tool,
    memory_search_tool, get_vectorstore_retriever_tool(),
]

def get_tool(name: str):
    return next((t for t in ALL_TOOLS if t.name == name), None)
