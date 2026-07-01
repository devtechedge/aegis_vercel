import os
import sys
import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

VERSION = "0.3.2"

app = FastAPI(title="AEGIS API", version=VERSION, description="Autonomous Enterprise Graph Intelligence System")

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

# Graceful router import
try:
    from routers import threads, fleet
    app.include_router(threads.router)
    app.include_router(fleet.router)
except Exception:
    pass

from pydantic import BaseModel
from typing import Any


class InvokeRequest(BaseModel):
    input: str
    thread_id: str = "default"
    force_demo: bool = False


class ResumeRequest(BaseModel):
    approved: bool = True
    comment: str | None = None
    payload: Any | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "online", "version": VERSION, "ui": "/ui", "docs": "/docs", "graph_loaded": bool(graph)}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": VERSION,
        "graph": bool(graph),
        "graph_error": graph_load_error,
        "llm_keys": {
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "langsmith": bool(os.getenv("LANGCHAIN_API_KEY")),
        },
    }


@app.get("/debug")
def debug():
    return {
        "graph_loaded": bool(graph),
        "graph_error": graph_load_error,
        "python": sys.version,
        "cwd": os.getcwd(),
    }


@app.post("/invoke")
async def invoke(req: InvokeRequest):
    if not graph:
        return {"output": f"[mock] {req.input}", "mock": True, "graph_error": graph_load_error}
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        result = await graph.ainvoke(
            {"task": req.input, "messages": [HumanMessage(content=req.input)]},
            config=config,
        )
        return {
            "output": result["messages"][-1].content if result.get("messages") else "",
            "artifacts": result.get("artifacts", {}),
            "confidence": result.get("confidence", 0),
            "needs_approval": result.get("needs_human_approval", False),
            "approval_payload": result.get("approval_payload"),
            "thread_id": req.thread_id,
        }
    except Exception as e:
        err = str(e)
        is_interrupt = "interrupt" in err.lower() or "GraphInterrupt" in type(e).__name__
        if is_interrupt:
            return {"interrupted": True, "message": err, "thread_id": req.thread_id}
        return {"error": err, "thread_id": req.thread_id}


# ── Inline HITL resume (works regardless of router imports) ────────────────

@app.post("/threads/{thread_id}/resume")
async def resume_thread(thread_id: str, req: ResumeRequest):
    if not graph:
        return {"thread_id": thread_id, "resumed": False, "error": "Graph not loaded"}
    try:
        from langgraph.types import Command
        config = {"configurable": {"thread_id": thread_id}}
        result = await graph.ainvoke(
            Command(resume={"approved": req.approved, "comment": req.comment}),
            config=config,
        )
        return {
            "thread_id": thread_id,
            "resumed": True,
            "confidence": result.get("confidence", 0),
            "needs_approval": result.get("needs_human_approval", False),
            "output": result["messages"][-1].content if result.get("messages") else "",
        }
    except Exception as e:
        return {"thread_id": thread_id, "resumed": False, "error": str(e)}


# ── Streaming ───────────────────────────────────────────────────────────────

DESCRIPTORS = {
    "supervisor": "Supervisor analyzing task and routing to next specialist",
    "researcher": "Researcher searching external sources and summarizing findings",
    "knowledge": "Knowledge retrieving relevant docs, runbooks and historical incidents",
    "sre_analyst": "SRE Analyst reviewing metrics, logs and running diagnostic analysis",
    "coder": "Coder generating patch and running tests in sandbox",
    "communicator": "Communicator composing final summary and incident report",
    "evaluator": "Evaluator scoring output quality and verifying against SLOs",
}


def _extract_text(node: str, update: dict) -> str:
    """Pull human-readable text from a node state update."""
    parts = []
    # Messages
    for m in update.get("messages", []):
        content = getattr(m, "content", "") if hasattr(m, "content") else str(m)
        if not content:
            continue
        # Skip raw supervisor routing JSON
        if node == "supervisor" and '"next"' in str(content):
            try:
                parsed = json.loads(content) if isinstance(content, str) else content
                if isinstance(parsed, dict) and "next" in parsed:
                    parts.append(f"  Route: {parsed.get('next', '?')}")
                    if parsed.get("reasoning"):
                        parts.append(f"  Reasoning: {parsed['reasoning'][:120]}")
                    continue
            except Exception:
                pass
        parts.append(content if len(str(content)) < 800 else str(content)[:800] + "...")

    # Routing decision (when returned as state key)
    next_agent = update.get("next_agent")
    if next_agent:
        parts.append(f"  Route -> {next_agent}" if next_agent != "finish" else "  Decision: FINISH")

    # Plan
    plan = update.get("plan")
    if plan and isinstance(plan, list):
        parts.append(f"  Plan: {' -> '.join(str(p) for p in plan)}")

    # Confidence
    conf = update.get("confidence")
    if conf is not None and conf > 0:
        parts.append(f"  Confidence: {conf:.0%}")

    # Artifacts
    arts = update.get("artifacts", {})
    if arts and isinstance(arts, dict):
        keys = list(arts.keys())
        if keys:
            parts.append(f"  Artifacts: {', '.join(keys)}")

    # HITL flag
    if update.get("needs_human_approval"):
        payload = update.get("approval_payload") or {}
        action = payload.get("type", "action") if isinstance(payload, dict) else "action"
        parts.append(f"  HITL: Approval required for {action}")

    header = f"[{node.upper()}] {DESCRIPTORS.get(node, node)}\n"
    return header + "\n".join(parts) if parts else header + "  (processing...)"


def _demo_event_gen():
    """Demo simulation — matches the recruiter-friendly output from v0.2.4."""
    step_events = [
        {"step": "supervisor", "description": "Supervisor analyzing task and routing to SRE Analyst"},
        {"step": "sre_analyst", "description": "SRE Analyst reviewing checkout metrics, logs and error rates"},
        {"step": "supervisor", "description": "Supervisor routing to Knowledge base for historical context"},
        {"step": "knowledge", "description": "Knowledge retrieving similar incidents, runbooks and past fixes"},
        {"step": "supervisor", "description": "Supervisor routing to Coder for remediation proposal"},
        {"step": "coder", "description": "Coder generating diagnostic script and proposed code changes"},
        {"step": "hitl", "description": "HITL interrupt triggered - awaiting human approval for code execution"},
        {"step": "evaluator", "description": "Evaluator validating proposed fix against SLOs and safety"},
        {"step": "communicator", "description": "Communicator preparing final summary, Slack notification and incident report"},
    ]
    # Metrics emitted at end for demo polish
    metric_events = [
        {"confidence": 96},
        {"artifacts": ["diagnostic_script.py", "patch.diff", "incident_report.md"]},
    ]
    nice_text = (
        "AEGIS has completed the investigation. "
        "The checkout latency spike in us-east was caused by database connection pool exhaustion during peak traffic. "
        "SRE Analyst identified elevated error rates in the payment service at 14:32 UTC. "
        "Knowledge base surfaced a similar incident from last quarter that was resolved by increasing pool size. "
        "Coder proposed increasing the pool size to 50 and adding circuit breakers with timeout handling. "
        "After human approval, Evaluator confirmed the fix maintains all SLO targets (p95 < 180ms). "
        "Communicator has prepared a detailed Slack summary, updated the incident report and notified the on-call team."
    )
    words = nice_text.split()
    word_idx = 0
    for step_ev in step_events:
        yield f"data: {json.dumps(step_ev)}\n\n"
        # Emit a few words per step for readable streaming
        end_word = min(word_idx + 6, len(words))
        for w in range(word_idx, end_word):
            token = words[w] + (" " if w < len(words) - 1 else "")
            yield f"data: {json.dumps({'token': token})}\n\n"
        word_idx = end_word
    for w in range(word_idx, len(words)):
        token = words[w] + (" " if w < len(words) - 1 else "")
        yield f"data: {json.dumps({'token': token})}\n\n"
    # Emit final metrics
    for me in metric_events:
        yield f"data: {json.dumps(me)}\n\n"


def _real_event_gen(task: str, thread_id: str):
    """Real graph streaming using astream(stream_mode='updates')."""
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": thread_id}}

    async def gen():
        try:
            async for mode, data in graph.astream(
                {"task": task, "messages": [HumanMessage(content=task)]},
                config=config,
                stream_mode="updates",
            ):
                # stream_mode="updates" yields (mode_str, {node_name: update_dict})
                for node_name, update in data.items():
                    # Emit step event (drives Mermaid visualizer)
                    desc = DESCRIPTORS.get(node_name, f"{node_name} executing")
                    yield f"data: {json.dumps({'step': node_name, 'description': desc})}\n\n"

                    # Emit readable text
                    text = _extract_text(node_name, update)
                    if text:
                        yield f"data: {json.dumps({'token': text + '\n\n'})}\n\n"

                    # HITL detection
                    if update.get("needs_human_approval"):
                        yield f"data: {json.dumps({'step': 'hitl', 'description': 'HITL interrupt - awaiting human approval'})}\n\n"

        except Exception as e:
            err = str(e)
            is_interrupt = "interrupt" in err.lower() or "GraphInterrupt" in type(e).__name__
            if is_interrupt:
                yield f"data: {json.dumps({'step': 'hitl', 'description': f'HITL interrupt: {err[:100]}'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': err})}\n\n"
        yield "data: [DONE]\n\n"

    return gen()


@app.post("/stream")
async def stream(req: InvokeRequest):
    if not graph or req.force_demo:
        # Graph not loaded or demo forced — use demo simulation
        return StreamingResponse(_demo_event_gen(), media_type="text/event-stream")

    # Graph loaded — use real streaming
    return StreamingResponse(
        _real_event_gen(req.input, req.thread_id),
        media_type="text/event-stream",
    )


# ── UI (preserved from v0.2.4 + Run Info panel + real HITL wiring) ────────

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>AEGIS v0.3.2</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
body{font-family: system-ui, -apple-system, sans-serif; background:#0b0f1a; color:#e8edf5; padding:24px; margin:0}
.container{display:grid; grid-template-columns: 1fr 480px; gap:24px; max-width:1260px; margin:0 auto}
.panel{background:#121826; border:1px solid #1e2639; border-radius:12px; padding:24px}
h1{margin:0 0 14px; font-size:26px}
h3{margin:0 0 12px; font-size:18px; color:#94a3b8}
textarea{width:100%; background:#0d1322; border:1px solid #1e2639; color:#e8edf5; border-radius:8px; padding:14px; font-family:inherit; font-size:15px; resize:vertical; line-height:1.5}
button{background:#6ea8fe; color:#081221; border:0; padding:12px 22px; border-radius:8px; font-weight:600; font-size:15px; cursor:pointer; margin-right:8px}
button:disabled{opacity:0.6; cursor:not-allowed}
#out{background:#0d1322; border:1px solid #1d2740; border-radius:8px; padding:18px; white-space:pre-wrap; min-height:240px; font-size:16px; line-height:1.6}
#graph{background:#0d1322; border:1px solid #1d2740; border-radius:8px; padding:14px; min-height:340px; font-size:14px}
#path{font-size:14px; color:#94a3b8; margin-top:10px; line-height:1.5}
#graph-log{font-size:13px; color:#94a3b8; margin-top:8px; max-height:80px; overflow:auto; white-space:pre-line; line-height:1.4}
a{color:#6ea8fe; text-decoration:none; font-size:14px}
a:hover{text-decoration:underline}
.status{font-size:15px; color:#94a3b8; margin-left:10px}
.hitl-box{margin-top:14px; padding:16px; background:#1a2233; border:1px solid #334155; border-radius:8px; font-size:15px}
/* Run Info Panel */
.info-bar{display:flex; gap:18px; margin-top:14px; flex-wrap:wrap}
.info-chip{background:#0d1322; border:1px solid #1d2740; border-radius:8px; padding:8px 16px; font-size:14px; color:#94a3b8; display:flex; align-items:center; gap:8px}
.info-chip .val{color:#e8edf5; font-weight:600; font-size:16px}
.mode-badge{font-size:11px; padding:3px 10px; border-radius:99px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px}
.mode-real{background:#0d2a1a; color:#22c55e; border:1px solid #16512e}
.mode-demo{background:#2a1a0d; color:#f59e0b; border:1px solid #5c3a00}
/* Toggle switch */
.toggle-row{display:flex; align-items:center; gap:12px; margin-bottom:14px}
.toggle-label{font-size:14px; color:#94a3b8}
.switch{position:relative; display:inline-block; width:44px; height:24px}
.switch input{opacity:0; width:0; height:0}
.slider{position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background:#1d2740; border-radius:24px; transition:.3s}
.slider:before{position:absolute; content:\"\"; height:18px; width:18px; left:3px; bottom:3px; background:#94a3b8; border-radius:50%; transition:.3s}
input:checked + .slider{background:#16512e}
input:checked + .slider:before{transform:translateX(20px); background:#22c55e}
</style>
</head>
<body>
<div class="container">
  <!-- LEFT: Console -->
  <div>
    <div class="panel">
      <div style="display:flex;align-items:center;gap:10px">
        <h1>AEGIS v0.3.2</h1>
        <span id="mode-badge" class="mode-badge mode-demo">checking...</span>
      </div>
      <div class="toggle-row">
        <label class="switch">
          <input type="checkbox" id="demo-toggle" checked>
          <span class="slider"></span>
        </label>
        <span class="toggle-label" id="toggle-text">Demo simulation (instant, no API calls)</span>
      </div>
      <textarea id="inp" rows="3">Investigate checkout latency spike in us-east.</textarea>
      <div style="margin:12px 0">
        <button id="run">Run AEGIS</button>
        <button id="stop" disabled>Stop</button>
        <span id="status" class="status"></span>
      </div>
      <pre id="out">Output will appear here...</pre>
      <!-- Run Info -->
      <div class="info-bar">
        <div class="info-chip"><span>Steps</span> <span class="val" id="info-steps">0</span></div>
        <div class="info-chip"><span>Confidence</span> <span class="val" id="info-conf">&mdash;</span></div>
        <div class="info-chip"><span>Artifacts</span> <span class="val" id="info-arts">0</span></div>
        <div class="info-chip"><span>Time</span> <span class="val" id="info-time">&mdash;</span></div>
      </div>
    </div>

    <!-- HITL -->
    <div id="hitl-panel" class="hitl-box" style="display:none">
      <strong>HITL: Approve code changes &amp; remediation?</strong><br>
      <button id="btn-approve" onclick="approveHITL(true)" style="background:#22c55e;color:#052e16">Approve</button>
      <button id="btn-reject" onclick="approveHITL(false)" style="background:#f87171;color:#3f1f1f">Reject</button>
      <span id="hitl-status" class="status"></span>
    </div>
  </div>

  <!-- RIGHT: Live Graph Visualizer -->
  <div class="panel">
    <h3>Live LangGraph Visualizer</h3>
    <div id="graph"></div>
    <div id="path"></div>
    <div id="graph-log"></div>
    <div style="margin-top:12px">
      <a href="https://smith.langchain.com" target="_blank">View full trace in LangSmith (aegis-production) &#8599;</a>
    </div>
    <div style="margin-top:12px;font-size:13px;color:#64748b">
      Expected path: supervisor &#8594; sre_analyst &#8594; supervisor &#8594; knowledge &#8594; supervisor &#8594; coder &#8594; [HITL] &#8594; evaluator &#8594; communicator
    </div>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const out = $('#out');
let controller = null;
let currentPath = [];
let mermaidReady = false;
let lastThread = '';
let stepCount = 0;
let artifactCount = 0;
let startTime = 0;
let timerInterval = null;

// Health check on load
let graphAvailable = false;
fetch('/health').then(r => r.json()).then(h => {
  const badge = $('#mode-badge');
  graphAvailable = !!h.graph;
  if (graphAvailable) {
    badge.textContent = 'LIVE';
    badge.className = 'mode-badge mode-real';
    $('#status').textContent = 'graph ready';
    // Toggle defaults to demo even when live
    $('#toggle-text').textContent = 'Demo simulation (toggle off for live inference)';
  } else {
    badge.textContent = 'DEMO';
    badge.className = 'mode-badge mode-demo';
    $('#status').textContent = 'demo mode';
    out.textContent = 'AEGIS graph not loaded. Running in demo simulation mode.\n\nSet GOOGLE_API_KEY in Vercel and redeploy for live inference.';
    // No toggle when no graph
    $('#demo-toggle').checked = true;
    $('#demo-toggle').disabled = true;
    $('#toggle-text').textContent = 'Demo only (no graph loaded)';
  }
}).catch(() => {
  $('#mode-badge').textContent = 'OFFLINE';
  $('#status').textContent = 'API unreachable';
});

// Toggle handler
$('#demo-toggle').onchange = function() {
  const on = this.checked;
  const badge = $('#mode-badge');
  if (graphAvailable) {
    badge.textContent = on ? 'DEMO' : 'LIVE';
    badge.className = 'mode-badge ' + (on ? 'mode-demo' : 'mode-real');
    $('#toggle-text').textContent = on ? 'Demo simulation (toggle off for live inference)' : 'Live inference (uses API keys, may be slow)';
    $('#status').textContent = on ? 'demo mode' : 'live mode';
  }
};

function initMermaid() {
  if (typeof mermaid !== 'undefined') {
    mermaid.initialize({ 
      startOnLoad: false, 
      theme: 'dark',
      flowchart: { curve: 'basis' }
    });
    mermaidReady = true;
  }
}

async function renderGraph(steps) {
  const el = $('#graph');
  if (!el || !mermaidReady) {
    el.innerHTML = '<div style="padding:40px;text-align:center;color:#64748b">Graph loading...</div>';
    return;
  }
  
  let m = `graph TD
    supervisor[Supervisor] --> sre_analyst[SRE Analyst]
    supervisor --> knowledge[Knowledge]
    supervisor --> coder[Coder]
    supervisor --> evaluator[Evaluator]
    supervisor --> communicator[Communicator]
    sre_analyst --> supervisor
    knowledge --> supervisor
    coder --> supervisor
    evaluator --> supervisor
    communicator --> supervisor
    supervisor -->|HITL interrupt| hitl[HITL]
    hitl --> evaluator
  `;
  
  m += `
classDef active fill:#6ea8fe,stroke:#081221,stroke-width:4px,color:#081221
classDef completed fill:#22c55e,stroke:#166534,stroke-width:2px,color:#052e16
classDef default fill:#1e2639,stroke:#3b4a6b,color:#e8edf5
  `;
  
  const last = steps.length ? steps[steps.length - 1] : '';
  
  steps.forEach((s, idx) => {
    if (s && idx < steps.length - 1) {
      m += `class ${s} completed\n`;
    }
  });
  
  if (last) {
    m += `class ${last} active\n`;
  }
  
  try {
    const { svg } = await mermaid.render('mermaid-diagram-' + Date.now(), m);
    el.innerHTML = svg;
  } catch (err) {
    el.innerHTML = '<pre style="color:#f66;font-size:11px">Mermaid render error</pre>';
  }
}

function addStep(step, description) {
  if (step === 'supervisor' || step === 'hitl' || !currentPath.includes(step)) {
    currentPath.push(step);
  }
  
  renderGraph(currentPath);
  
  const pathEl = $('#path');
  if (pathEl) {
    pathEl.innerHTML = '<strong>Current path:</strong><br>' + currentPath.join(' &#8594; ');
  }
  
  const logEl = $('#graph-log');
  if (logEl && description) {
    logEl.textContent += (logEl.textContent ? '\n' : '') + '\u2022 ' + description;
    logEl.scrollTop = logEl.scrollHeight;
  }
  
  if (step === 'hitl') {
    const hitl = $('#hitl-panel');
    if (hitl) hitl.style.display = 'block';
  }
}

function updateTimer() {
  if (!startTime) return;
  const s = ((Date.now() - startTime) / 1000).toFixed(1);
  $('#info-time').textContent = s + 's';
}

async function approveHITL(approved) {
  const hitlPanel = $('#hitl-panel');
  const btnApprove = $('#btn-approve');
  const btnReject = $('#btn-reject');
  const hitlStatus = $('#hitl-status');

  btnApprove.disabled = true;
  btnReject.disabled = true;
  hitlStatus.textContent = 'sending...';

  const msg = approved 
    ? '\n\n[HITL APPROVED] Human approved code changes. Resuming graph execution...'
    : '\n\n[HITL REJECTED] Human rejected the proposed changes. Stopping.';
  out.textContent += msg;
  out.scrollTop = out.scrollHeight;

  // Call real resume endpoint
  try {
    const res = await fetch('/threads/' + encodeURIComponent(lastThread) + '/resume', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({approved: approved, comment: approved ? 'approved via UI' : 'rejected via UI'})
    });
    const j = await res.json();

    if (j.resumed) {
      hitlStatus.textContent = 'resumed OK';
      hitlStatus.style.color = '#22c55e';
      if (j.output) {
        out.textContent += '\n\n' + j.output;
        out.scrollTop = out.scrollHeight;
      }
      if (j.confidence) {
        $('#info-conf').textContent = (j.confidence * 100).toFixed(0) + '%';
      }
    } else {
      hitlStatus.textContent = 'resume failed: ' + (j.error || 'unknown');
      hitlStatus.style.color = '#f87171';
    }
  } catch (e) {
    hitlStatus.textContent = 'API error: ' + e;
    hitlStatus.style.color = '#f87171';
  }

  const pathEl = $('#path');
  if (pathEl) {
    pathEl.innerHTML = pathEl.innerHTML + (approved ? ' &#8594; approved' : ' &#8594; rejected');
  }

  setTimeout(() => {
    hitlPanel.style.display = 'none';
    btnApprove.disabled = false;
    btnReject.disabled = false;
    hitlStatus.textContent = '';
  }, 2000);
}

async function runStream() {
  out.textContent = '';
  $('#run').disabled = true;
  $('#stop').disabled = false;
  $('#status').textContent = 'running...';

  const hitl = $('#hitl-panel');
  if (hitl) hitl.style.display = 'none';
  
  currentPath = [];
  stepCount = 0;
  artifactCount = 0;
  startTime = Date.now();
  $('#info-steps').textContent = '0';
  $('#info-conf').textContent = '\u2014';
  $('#info-arts').textContent = '0';
  $('#info-time').textContent = '0.0s';

  const pathEl = $('#path');
  if (pathEl) pathEl.innerHTML = '';
  const logEl = $('#graph-log');
  if (logEl) logEl.textContent = '';
  
  renderGraph(currentPath);
  clearInterval(timerInterval);
  timerInterval = setInterval(updateTimer, 200);
  
  const task = $('#inp').value;
  lastThread = 'web-' + Date.now();
  controller = new AbortController();

  try {
    const res = await fetch('/stream', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({input: task, thread_id: lastThread, force_demo: $('#demo-toggle').checked}),
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
          if (j.token) {
            out.textContent += j.token;
            out.scrollTop = out.scrollHeight;
            // Extract metrics from text
            const cm = j.token.match(/Confidence:\s*(\d+%)/);
            if (cm) $('#info-conf').textContent = cm[1];
            const am = j.token.match(/Artifacts:\s*(.+)/);
            if (am) { artifactCount += am[1].split(',').length; $('#info-arts').textContent = artifactCount; }
          }
          if (j.step) {
            stepCount++;
            $('#info-steps').textContent = stepCount;
            addStep(j.step, j.description || '');
          }
          if (j.confidence !== undefined) {
            $('#info-conf').textContent = j.confidence + '%';
          }
          if (j.artifacts) {
            artifactCount = j.artifacts.length;
            $('#info-arts').textContent = artifactCount;
          }
          if (j.error) {
            out.textContent += '\n[error] ' + j.error;
          }
        } catch (e) {}
      }
    }
    clearInterval(timerInterval);
    updateTimer();
    $('#status').textContent = 'done';
  } catch (e) {
    if (e.name !== 'AbortError') out.textContent += '\n[error] ' + e;
    $('#status').textContent = 'stopped';
    clearInterval(timerInterval);
  } finally {
    $('#run').disabled = false;
    $('#stop').disabled = true;
    controller = null;
  }
}

$('#run').onclick = runStream;
$('#stop').onclick = () => {
  if (controller) controller.abort();
};

window.onload = () => {
  initMermaid();
  setTimeout(() => {
    renderGraph([]);
    const pathEl = $('#path');
    if (pathEl) pathEl.innerHTML = '<em>Graph will animate live during run</em>';
  }, 80);
};
</script>
</body>
</html>"""