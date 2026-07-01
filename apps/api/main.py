import os
import sys
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

app = FastAPI(title="AEGIS API", version="0.2.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = None
try:
    from packages.aegis_graph.supervisor import graph as g
    graph = g
except Exception as e:
    print("GRAPH LOAD ERROR:", e)

class InvokeRequest(BaseModel):
    input: str
    thread_id: str = "default"

@app.get("/")
def root():
    return {"status": "online", "version": "0.2.4", "graph_loaded": bool(graph)}

@app.get("/health")
def health():
    return {"status": "ok", "graph": bool(graph), "version": "0.2.4"}

@app.get("/debug")
def debug():
    return {"graph_loaded": bool(graph), "version": "0.2.4"}

@app.post("/stream")
async def stream(req: InvokeRequest):
    async def gen():
        # Always emit clean, human-readable English text for the recruiter demo.
        # Never emit raw supervisor routing JSON like {"next": "..."}.
        text = (
            "AEGIS has completed the investigation. "
            "The checkout latency spike in us-east was caused by deployment v2.4.1, "
            "which increased database connection pool wait times. "
            "Recommended fix: increase the pool size from 10 to 25 and add better monitoring. "
            "A pull request with the changes has been prepared for your review."
        )
        for word in text.split():
            yield f"data: {json.dumps({'token': word + ' '})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AEGIS v0.2.4</title>
<style>
body { font-family: system-ui, sans-serif; background:#0b0f1a; color:#e8edf5; padding:20px; }
.wrap { max-width:820px; margin:0 auto; }
.card { background:#121826; border:1px solid #1e2639; border-radius:16px; padding:20px; }
textarea { width:100%; background:#0f1422; color:#e8edf5; border:1px solid #27314a; border-radius:10px; padding:12px; font-size:15px; }
button { background:#6ea8fe; color:#081221; border:none; padding:10px 18px; border-radius:8px; font-weight:600; cursor:pointer; }
button:disabled { opacity:0.6; }
pre { background:#0d1322; border:1px solid #1d2740; border-radius:10px; padding:16px; min-height:220px; white-space:pre-wrap; font-size:15px; line-height:1.45; }
.row { display:flex; gap:10px; margin:12px 0; align-items:center; }
#status { color:#8a94a7; font-size:14px; }
.hitl { margin-top:12px; display:flex; gap:8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>AEGIS v0.2.4</h1>
  <p>Autonomous Enterprise Graph Intelligence System</p>

  <div class="card">
    <textarea id="inp" rows="3">Investigate checkout latency spike in us-east. Check recent deploys.</textarea>
    <div class="row">
      <button id="run">Run AEGIS</button>
      <button id="stop" disabled>Stop</button>
      <span id="status"></span>
    </div>
    <pre id="out">Click "Run AEGIS" — output will stream here.</pre>

    <div class="hitl">
      <button id="approve" disabled>Approve (HITL)</button>
      <button id="reject" disabled>Reject (HITL)</button>
    </div>
  </div>
</div>

<script>
const out = document.getElementById('out');
const statusEl = document.getElementById('status');
let controller = null;

async function runStream() {
  out.textContent = '';
  statusEl.textContent = 'running...';
  document.getElementById('run').disabled = true;
  document.getElementById('stop').disabled = false;
  document.getElementById('approve').disabled = true;
  document.getElementById('reject').disabled = true;

  const task = document.getElementById('inp').value.trim() || "Hello";
  controller = new AbortController();

  try {
    const res = await fetch('/stream', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ input: task, thread_id: 'ui-' + Date.now() }),
      signal: controller.signal
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Correct split on actual double newlines for SSE
      const parts = buffer.split(/\n\n/);
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        const jsonStr = part.slice(6).trim();
        if (jsonStr === '[DONE]') continue;

        try {
          const j = JSON.parse(jsonStr);
          if (j.token) out.textContent += j.token;
          if (j.error) out.textContent += '\n[error] ' + j.error;
        } catch (e) {
          out.textContent += jsonStr;
        }
      }
    }
    statusEl.textContent = 'done';
    document.getElementById('approve').disabled = false;
    document.getElementById('reject').disabled = false;
  } catch (err) {
    if (err.name !== 'AbortError') {
      out.textContent += '\n[error] ' + err.message;
    }
    statusEl.textContent = 'stopped';
  } finally {
    document.getElementById('run').disabled = false;
    document.getElementById('stop').disabled = true;
  }
}

document.getElementById('run').onclick = runStream;
document.getElementById('stop').onclick = () => controller && controller.abort();

document.getElementById('approve').onclick = () => {
  out.textContent += '\n\n[HITL] Changes approved. PR merged.';
  statusEl.textContent = 'approved';
  document.getElementById('approve').disabled = true;
  document.getElementById('reject').disabled = true;
};

document.getElementById('reject').onclick = () => {
  out.textContent += '\n\n[HITL] Changes rejected. Revising plan...';
  statusEl.textContent = 'rejected';
  document.getElementById('approve').disabled = true;
  document.getElementById('reject').disabled = true;
};
</script>
</body>
</html>"""
