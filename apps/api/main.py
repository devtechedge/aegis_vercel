import os
import sys
import traceback
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = FastAPI(title="AEGIS API", version="0.2.3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = None
graph_load_error = None

try:
    from packages.aegis_graph.supervisor import graph as aegis_graph
    graph = aegis_graph
except Exception as e:
    graph_load_error = str(e)

from pydantic import BaseModel

class InvokeRequest(BaseModel):
    input: str
    thread_id: str = "default"

@app.get("/")
def root():
    return {"status": "online", "version": "0.2.3", "ui": "/ui", "graph_loaded": bool(graph)}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.2.3",
        "graph": bool(graph),
        "graph_error": graph_load_error,
        "llm_keys": {
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "langsmith": bool(os.getenv("LANGCHAIN_API_KEY")),
        }
    }

@app.get("/debug")
def debug():
    return {"graph_loaded": bool(graph), "graph_error": graph_load_error}

@app.post("/invoke")
async def invoke(req: InvokeRequest):
    if not graph:
        return {"output": f"[mock] {req.input}", "mock": True}
    from langchain_core.messages import HumanMessage
    try:
        result = await graph.ainvoke(
            {"task": req.input, "messages": [HumanMessage(content=req.input)]},
            config={"configurable": {"thread_id": req.thread_id}}
        )
        return {
            "output": result.get("messages", [{}])[-1].get("content", ""),
            "thread_id": req.thread_id
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/stream")
async def stream(req: InvokeRequest):
    if not graph:
        async def mock():
            yield 'data: {"token": "Mock response from AEGIS (graph not loaded on this deploy). "}\n\n'
            yield 'data: {"token": "Try setting GOOGLE_API_KEY in Vercel."}\n\n'
            yield "data: [DONE]\n\n"
        return StreamingResponse(mock(), media_type="text/event-stream")

    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": req.thread_id}}

    async def event_gen():
        try:
            async for event in graph.astream_events(
                {"task": req.input, "messages": [HumanMessage(content=req.input)]},
                config=config, version="v2"
            ):
                if event.get("event") == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    token = getattr(chunk, "content", "") if chunk else ""
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AEGIS v0.2.3</title>
<style>
body{font-family:sans-serif;background:#0b0f1a;color:#e8edf5;padding:20px}
.card{background:#121826;border:1px solid #1e2639;border-radius:12px;padding:20px;max-width:800px;margin:auto}
button{background:#6ea8fe;color:#081221;border:0;padding:10px 18px;border-radius:8px;font-weight:600;cursor:pointer}
pre{background:#0d1322;border:1px solid #1d2740;border-radius:8px;padding:16px;white-space:pre-wrap;min-height:160px}
</style>
</head>
<body>
<div class="card">
  <h1>AEGIS v0.2.3</h1>
  <textarea id="inp" rows="3" style="width:100%">Investigate checkout latency spike in us-east.</textarea>
  <div style="margin:12px 0">
    <button id="run">Run AEGIS</button>
    <button id="stop" disabled>Stop</button>
    <span id="status"></span>
  </div>
  <pre id="out">Output will appear here...</pre>
</div>

<script>
const $ = s => document.querySelector(s);
const out = $('#out');
let controller = null;

async function runStream() {
  out.textContent = '';
  $('#run').disabled = true;
  $('#stop').disabled = false;
  $('#status').textContent = 'running...';

  const task = $('#inp').value;
  controller = new AbortController();

  try {
    const res = await fetch('/stream', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({input: task, thread_id: 'web-' + Date.now()}),
      signal: controller.signal
    });

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buf += dec.decode(value, {stream: true});

      const parts = buf.split(/\n\n/);
      buf = parts.pop() || '';

      for (const p of parts) {
        if (!p.startsWith('data: ')) continue;
        const d = p.slice(6).trim();
        if (d === '[DONE]') continue;
        try {
          const j = JSON.parse(d);
          if (j.token) out.textContent += j.token;
          if (j.error) out.textContent += '\n[error] ' + j.error;
        } catch {}
      }
    }
    $('#status').textContent = 'done';
  } catch (e) {
    out.textContent += '\n[error] ' + e;
    $('#status').textContent = 'stopped';
  } finally {
    $('#run').disabled = false;
    $('#stop').disabled = true;
  }
}

$('#run').onclick = runStream;
$('#stop').onclick = () => controller && controller.abort();
</script>
</body>
</html>"""
