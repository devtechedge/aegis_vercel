import os
import sys
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json

# Ensure packages/ is importable both locally and on Vercel
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print("=== AEGIS API STARTING ===")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

app = FastAPI(title="AEGIS API", version="0.2.0", description="Autonomous Enterprise Graph Intelligence System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("\n--- Attempting router imports ---")
try:
    from apps.api.routers import threads, fleet
    app.include_router(threads.router)
    app.include_router(fleet.router)
    print("✅ SUCCESS: Imported threads and fleet routers")
except Exception as e:
    print(f"❌ FAILED: Router import error - {type(e).__name__}: {e}")
    traceback.print_exc()
    # Vercel fallback - local import
    try:
        from routers import threads, fleet
        app.include_router(threads.router)
        app.include_router(fleet.router)
        print("✅ Fallback routers imported")
    except Exception:
        pass

# --- LangGraph / LangServe ---
graph = None
aegis_runnable = None
print("\n--- Attempting LangGraph import ---")
try:
    from packages.aegis_graph.supervisor import graph as aegis_graph, aegis_runnable as runnable
    graph = aegis_graph
    aegis_runnable = runnable
    print("✅ SUCCESS: AEGIS graph loaded")
    # LangServe routes
    try:
        from langserve import add_routes
        add_routes(app, aegis_runnable, path="/aegis")
        print("✅ LangServe routes at /aegis")
    except Exception as e:
        print(f"LangServe add_routes failed: {e}")
except Exception as e:
    print(f"❌ LangGraph import failed: {e}")
    traceback.print_exc()

print("\n=== AEGIS API INITIALIZATION COMPLETE ===\n")

@app.get("/")
async def root():
    return {"status": "online", "message": "AEGIS API is running", "docs": "/docs", "version": "0.2.0", "graph_loaded": graph is not None}

@app.get("/health")
def health():
    return {"status": "ok", "products": ["Engine","Observability","Evaluation","Deployment","Sandboxes","Fleet","deepagents","langgraph","langchain"], "version": "0.2.0", "graph": bool(graph)}

@app.get("/debug")
def debug_info():
    return {"cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH"), "python_version": sys.version, "graph_loaded": bool(graph)}

# --- LangServe-compatible endpoints ---
from pydantic import BaseModel
class InvokeRequest(BaseModel):
    input: str
    thread_id: str = "default"

@app.post("/invoke")
async def invoke(req: InvokeRequest):
    if not graph:
        return {"error": "Graph not loaded - missing dependencies?", "output": f"[mock] {req.input}"}
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        result = await graph.ainvoke({"task": req.input, "messages": [HumanMessage(content=req.input)]}, config=config)
        return {"output": result["messages"][-1].content if result.get("messages") else "", "artifacts": result.get("artifacts", {}), "confidence": result.get("confidence", 0), "needs_approval": result.get("needs_human_approval", False), "approval_payload": result.get("approval_payload")}
    except Exception as e:
        # Check for interrupt
        if "interrupt" in str(type(e)).lower() or "GraphInterrupt" in str(e):
            return {"interrupted": True, "message": str(e)}
        raise

@app.post("/stream")
async def stream(req: InvokeRequest):
    if not graph:
        async def mock_gen():
            yield f"data: {json.dumps({'token': 'AEGIS mock stream - set API keys for full graph'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(mock_gen(), media_type="text/event-stream")
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": req.thread_id}}
    async def event_gen():
        try:
            async for event in graph.astream_events({"task": req.input, "messages": [HumanMessage(content=req.input)]}, config=config, version="v2"):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    token = event["data"].get("chunk", {}).content if hasattr(event["data"].get("chunk", {}), "content") else ""
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                elif kind == "on_chain_end":
                    yield f"data: {json.dumps({'event': kind})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream")

# threads resume is in routers/threads.py
