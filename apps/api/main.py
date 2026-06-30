import os
import sys
import traceback
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse

# Ensure packages/ is importable both locally and on Vercel
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print("=== AEGIS API STARTING ===")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

app = FastAPI(title="AEGIS API", version="0.2.3", description="Autonomous Enterprise Graph Intelligence System")

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
graph_load_error = None
print("\n--- Attempting LangGraph import ---")
try:
    from packages.aegis_graph.supervisor import graph as aegis_graph, aegis_runnable as runnable
    graph = aegis_graph
    aegis_runnable = runnable
    print("✅ SUCCESS: AEGIS graph loaded")
    try:
        from langserve import add_routes
        add_routes(app, aegis_runnable, path="/aegis")
        print("✅ LangServe routes at /aegis")
    except Exception as e:
        print(f"LangServe add_routes failed: {e}")
except Exception as e:
    graph_load_error = f"{type(e).__name__}: {e}"
    print(f"❌ LangGraph import failed: {graph_load_error}")
    traceback.print_exc()

print("\n=== AEGIS API INITIALIZATION COMPLETE ===\n")

@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return {"status": "online", "message": "AEGIS API is running", "docs": "/docs", "ui": "/ui", "version": "0.2.3", "graph_loaded": graph is not None, "graph_error": graph_load_error}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "products": ["Engine","Observability","Evaluation","Deployment","Sandboxes","Fleet","deepagents","langgraph","langchain"],
        "version": "0.2.3",
        "graph": bool(graph),
        "graph_error": graph_load_error,
        "llm_keys": {
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "langsmith": bool(os.getenv("LANGCHAIN_API_KEY")),
            "tavily": bool(os.getenv("TAVILY_API_KEY")),
        }
    }

@app.get("/debug")
def debug_info():
    return {"cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH"), "python_version": sys.version, "graph_loaded": bool(graph), "graph_error": graph_load_error}

# --- LangServe-compatible endpoints ---
from pydantic import BaseModel

class InvokeRequest(BaseModel):
    input: str
    thread_id: str = "default"

@app.post("/invoke")
async def invoke(req: InvokeRequest):
    if not graph:
        return {"error": "Graph not loaded", "graph_error": graph_load_error, "output": f"[mock] {req.input}", "mock": True}
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        result = await graph.ainvoke({"task": req.input, "messages": [HumanMessage(content=req.input)]}, config=config)
        return {
            "output": result["messages"][-1].content if result.get("messages") else "",
            "artifacts": result.get("artifacts", {}),
            "confidence": result.get("confidence", 0),
            "needs_approval": result.get("needs_human_approval", False),
            "approval_payload": result.get("approval_payload"),
            "thread_id": req.thread_id
        }
    except Exception as e:
        if "interrupt" in str(type(e)).lower() or "GraphInterrupt" in str(e):
            return {"interrupted": True, "message": str(e), "thread_id": req.thread_id}
        raise

@app.post("/stream")
async def stream(req: InvokeRequest):
    if not graph:
        async def mock_gen():
            msg = f"AEGIS mock stream – graph not loaded. Error: {graph_load_error or 'missing deps'}. Set GOOGLE_API_KEY + LANGCHAIN_API_KEY in Vercel, Install Command = pip install -r requirements-vercel.txt, redeploy."
            for w in msg.split(" "):
                yield f"data: {json.dumps({'token': w+' '})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(mock_gen(), media_type="text/event-stream")

    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_gen():
        try:
            async for event in graph.astream_events({"task": req.input, "messages": [HumanMessage(content=req.input)]}, config=config, version="v2"):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    token = getattr(chunk, "content", "") if chunk else ""
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

# --- Built-in Chat UI (Basic reliable version for recruiters) ---
@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AEGIS – Autonomous Enterprise Graph Intelligence</title>
<style>
:root{--bg:#0b0f1a;--card:#121826;--mut:#8a94a7;--acc:#6ea8fe;--ok:#22c55e}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:#e8edf5}
.wrap{max-width:880px;margin:40px auto;padding:0 20px}
h1{font-size:28px;margin:0 0 4px} .sub{color:var(--mut);margin-bottom:18px}
.card{background:var(--card);border:1px solid #1e2639;border-radius:16px;padding:18px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
textarea{width:100%;background:#0f1422;color:#e8edf5;border:1px solid #27314a;border-radius:12px;padding:12px;font-size:15px;resize:vertical}
button{background:var(--acc);color:#081221;border:0;padding:10px 16px;border-radius:10px;font-weight:600;cursor:pointer}
button:disabled{opacity:.6;cursor:not-allowed}
pre{white-space:pre-wrap;background:#0d1322;border:1px solid #1d2740;border-radius:12px;padding:14px;min-height:140px;overflow:auto}
.row{display:flex;gap:10px;align-items:center;margin-top:10px;flex-wrap:wrap}
.badge{font-size:12px;color:#9aabbF;background:#0f172a;border:1px solid #1e293b;padding:4px 8px;border-radius:999px}
a{color:#8ab4ff}
small{color:var(--mut)}
#status{margin-left:8px;color:var(--mut)}
</style>
</head>
<body>
<div class="wrap">
<h1>AEGIS v0.2.3</h1>
<div class="sub">Autonomous Enterprise Graph Intelligence System — LangGraph Supervisor + 6 specialists • <a href="/docs" target="_blank">API docs</a> • <a href="https://github.com/devtechedge/aegis_vercel" target="_blank">GitHub</a></div>

<div class="card">
<textarea id="inp" rows="3">Investigate checkout latency spike in us-east. Check recent deploys, run a runbook, summarize related Slack threads, and open a PR if safe.</textarea>
<div class="row">
<button id="run">Run AEGIS</button>
<button id="stop" disabled>Stop</button>
<span id="status"></span>
</div>
<pre id="out">Output will stream here…

Tip: Set GOOGLE_API_KEY + LANGCHAIN_API_KEY in Vercel for live Gemini inference. Without keys, you'll see a mock stream with setup instructions.</pre>
<div class="row" id="approval" style="display:none">
<strong>HITL Approval required:</strong>
<span id="approval_payload" style="color:#9aabbF;font-size:13px"></span>
<button id="approve">Approve ✅</button>
<button id="reject">Reject ❌</button>
</div>
</div>

<p><small>
Endpoints: <code>POST /invoke</code> • <code>POST /stream</code> • <code>POST /threads/{id}/resume</code><br>
Live API: <a href="/health">/health</a> • <a href="/debug">/debug</a>
</small></p>
</div>
<script>
const $ = s => document.querySelector(s);
const out = $('#out'), statusEl = $('#status');
let controller = null;
let lastThread = 'web-' + Math.random().toString(36).slice(2);

async function runStream(){
  out.textContent = '';
  $('#approval').style.display = 'none';
  $('#run').disabled = true;
  $('#stop').disabled = false;
  statusEl.textContent = 'running…';
  const task = $('#inp').value;
  controller = new AbortController();
  try{
    const res = await fetch('/stream', {
      method:'POST',
      headers:{'content-type':'application/json'},
      body: JSON.stringify({input: task, thread_id: lastThread}),
      signal: controller.signal
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while(true){
      const {done, value} = await reader.read();
      if(done) break;
      buf += dec.decode(value, {stream:true});
      // FIXED: Use regex split to avoid escape issues
      const parts = buf.split(/\n\n/);
      buf = parts.pop();
      for(const p of parts){
        if(!p.startsWith('data: ')) continue;
        const d = p.slice(6).trim();
        if(d === '[DONE]') continue;
        try{
          const j = JSON.parse(d);
          if(j.token) out.textContent += j.token;
          if(j.error) out.textContent += '\n[error] ' + j.error;
        }catch(e){
          // ignore parse errors for partial chunks
        }
      }
    }
    statusEl.textContent = 'done';
    // Check if HITL is needed
    try{
      const chk = await fetch('/invoke', {
        method:'POST',
        headers:{'content-type':'application/json'},
        body: JSON.stringify({input: task, thread_id: lastThread})
      });
      const jc = await chk.json();
      if(jc.needs_approval){
        $('#approval_payload').textContent = JSON.stringify(jc.approval_payload || {}).slice(0,180);
        $('#approval').style.display = 'flex';
      }
    }catch{}
  }catch(e){
    if(e.name !== 'AbortError') out.textContent += '\n[stream error] ' + e;
    statusEl.textContent = 'stopped';
  }finally{
    $('#run').disabled = false;
    $('#stop').disabled = true;
    controller = null;
  }
}

$('#run').onclick = runStream;
$('#stop').onclick = () => controller && controller.abort();

async function doResume(approved){
  statusEl.textContent = approved ? 'resuming (approved)…' : 'resuming (rejected)…';
  const res = await fetch('/threads/' + encodeURIComponent(lastThread) + '/resume', {
    method:'POST',
    headers:{'content-type':'application/json'},
    body: JSON.stringify({approved, comment: approved ? 'approved via UI' : 'rejected via UI'})
  });
  const j = await res.json();
  out.textContent += '\n\n--- HITL resume: ' + (j.resumed ? 'OK' : 'failed') + ' ---\n' + JSON.stringify(j, null, 2);
  $('#approval').style.display = 'none';
  statusEl.textContent = 'done';
}

$('#approve').onclick = () => doResume(true);
$('#reject').onclick = () => doResume(false);

// show health on load
fetch('/health').then(r => r.json()).then(h => {
  statusEl.textContent = h.graph ? 'graph ready ✅' : 'graph not loaded – set GOOGLE_API_KEY + LANGCHAIN_API_KEY in Vercel';
}).catch(() => {});
</script>
</body>
</html>"""

# threads resume is in routers/threads.py