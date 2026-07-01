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

VERSION = "0.4.0"

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


@app.post("/threads/{thread_id}/resume/stream")
async def resume_thread_stream(thread_id: str, req: ResumeRequest):
    """SSE streaming resume — runs remaining nodes (evaluator, communicator) after HITL."""
    if not graph:
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'Graph not loaded'})}\n\n", "data: [DONE]\n\n"]),
            media_type="text/event-stream",
        )
    from langgraph.types import Command

    def _normalize_chunk(chunk):
        if isinstance(chunk, dict):
            return chunk
        if isinstance(chunk, tuple) and len(chunk) == 2:
            first, second = chunk
            if isinstance(second, dict) and any(k in DESCRIPTORS for k in second):
                return second
            return {first: second} if isinstance(second, dict) else {str(first): second}
        return chunk if isinstance(chunk, dict) else {"unknown": chunk}

    async def gen():
        try:
            config = {"configurable": {"thread_id": thread_id}}
            async for chunk in graph.astream(
                Command(resume={"approved": req.approved, "comment": req.comment}),
                config=config,
                stream_mode="updates",
            ):
                data = _normalize_chunk(chunk)
                for node_name, update in data.items():
                    if node_name.startswith("__"):
                        continue
                    if not isinstance(update, dict):
                        update = {"messages": update}
                    desc = DESCRIPTORS.get(node_name, f"{node_name} executing")
                    yield f"data: {json.dumps({'step': node_name, 'description': desc})}\n\n"
                    text = _extract_text(node_name, update)
                    if text:
                        yield f"data: {json.dumps({'token': text + '\n\n'})}\n\n"
        except Exception as e:
            err = str(e)
            yield f"data: {json.dumps({'error': err})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


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
    parts = []
    # Only use the LAST message from each node — earlier messages are
    # accumulated history from previous agents and cause duplicate output.
    messages = update.get("messages", [])
    if messages:
        m = messages[-1]
        content = getattr(m, "content", "") if hasattr(m, "content") else str(m)
        if content:
            if node == "supervisor" and '"next"' in str(content):
                try:
                    parsed = json.loads(content) if isinstance(content, str) else content
                    if isinstance(parsed, dict) and "next" in parsed:
                        parts.append(f"  Route: {parsed.get('next', '?')}")
                        if parsed.get("reasoning"):
                            parts.append(f"  Reasoning: {parsed['reasoning'][:120]}")
                except Exception:
                    pass
            else:
                parts.append(content if len(str(content)) < 800 else str(content)[:800] + "...")

    next_agent = update.get("next_agent")
    if next_agent:
        parts.append(f"  Route -> {next_agent}" if next_agent != "finish" else "  Decision: FINISH")

    plan = update.get("plan")
    if plan and isinstance(plan, list):
        parts.append(f"  Plan: {' -> '.join(str(p) for p in plan)}")

    conf = update.get("confidence")
    if conf is not None and conf > 0:
        parts.append(f"  Confidence: {conf:.0%}")

    arts = update.get("artifacts", {})
    if arts and isinstance(arts, dict):
        keys = list(arts.keys())
        if keys:
            parts.append(f"  Artifacts: {', '.join(keys)}")

    if update.get("needs_human_approval"):
        payload = update.get("approval_payload") or {}
        action = payload.get("type", "action") if isinstance(payload, dict) else "action"
        parts.append(f"  HITL: Approval required for {action}")

    header = f"[{node.upper()}] {DESCRIPTORS.get(node, node)}\n"
    return header + "\n".join(parts) if parts else header + "  (processing...)"


def _demo_event_gen():
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
        end_word = min(word_idx + 6, len(words))
        for w in range(word_idx, end_word):
            token = words[w] + (" " if w < len(words) - 1 else "")
            yield f"data: {json.dumps({'token': token})}\n\n"
        word_idx = end_word
    for w in range(word_idx, len(words)):
        token = words[w] + (" " if w < len(words) - 1 else "")
        yield f"data: {json.dumps({'token': token})}\n\n"
    yield f"data: {json.dumps({'confidence': 96, 'artifacts': ['diagnostic_script.py', 'patch.diff', 'incident_report.md']})}\n\n"


def _real_event_gen(task: str, thread_id: str):
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": thread_id}}

    def _normalize_chunk(chunk):
        """Handle different LangGraph versions returning different astream shapes.

        LangGraph has changed astream(stream_mode="updates") return format across versions:
          - Some yield (mode_str, {node_name: update_dict})  — newest
          - Some yield (node_name, update_dict)               — older
          - Some yield {node_name: update_dict}               — no tuple

        This normalises all three into {node_name: update_dict}.
        """
        # Case 1: bare dict — already {node_name: update}
        if isinstance(chunk, dict):
            return chunk
        # Case 2 & 3: tuple of 2
        if isinstance(chunk, tuple) and len(chunk) == 2:
            first, second = chunk
            # If second is a dict whose keys include agent names → (mode, {node: update})
            if isinstance(second, dict) and any(k in DESCRIPTORS for k in second):
                return second
            # Otherwise → (node_name, update_dict) — old format
            return {first: second} if isinstance(second, dict) else {str(first): second}
        # Fallback: treat as single dict
        return chunk if isinstance(chunk, dict) else {"unknown": chunk}

    async def gen():
        try:
            async for chunk in graph.astream(
                {"task": task, "messages": [HumanMessage(content=task)]},
                config=config,
                stream_mode="updates",
            ):
                data = _normalize_chunk(chunk)
                for node_name, update in data.items():
                    # Skip LangGraph internal interrupt nodes —
                    # handled cleanly by the HITL event below.
                    if node_name.startswith("__"):
                        continue
                    if not isinstance(update, dict):
                        update = {"messages": update}
                    desc = DESCRIPTORS.get(node_name, f"{node_name} executing")
                    yield f"data: {json.dumps({'step': node_name, 'description': desc})}\n\n"
                    text = _extract_text(node_name, update)
                    if text:
                        yield f"data: {json.dumps({'token': text + '\n\n'})}\n\n"
                    if update.get("needs_human_approval"):
                        yield f"data: {json.dumps({'step': 'hitl', 'description': 'HITL interrupt - awaiting human approval'})}\n\n"
        except Exception as e:
            err = str(e)
            is_interrupt = "interrupt" in err.lower() or "GraphInterrupt" in type(e).__name__
            if is_interrupt:
                yield f"data: {json.dumps({'step': 'hitl', 'description': 'HITL interrupt - awaiting human approval'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': err})}\n\n"
        yield "data: [DONE]\n\n"

    return gen()


@app.post("/stream")
async def stream(req: InvokeRequest):
    if not graph or req.force_demo:
        return StreamingResponse(_demo_event_gen(), media_type="text/event-stream")
    return StreamingResponse(
        _real_event_gen(req.input, req.thread_id),
        media_type="text/event-stream",
    )


# ── UI ──────────────────────────────────────────────────────────────────────

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    return r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AEGIS v0.4.0</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root {
  --bg-deep: #06080e;
  --bg-panel: #0c1220;
  --bg-input: #0a0f1c;
  --border: #1a2540;
  --border-glow: #1e3a5f;
  --text: #e2e8f4;
  --text-muted: #7b8ba8;
  --accent: #38bdf8;
  --accent-glow: rgba(56,189,248,0.25);
  --green: #34d399;
  --green-glow: rgba(52,211,153,0.2);
  --red: #f87171;
  --amber: #fbbf24;
  --radius: 14px;
}

body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--bg-deep);
  color: var(--text);
  padding: 28px;
  min-height: 100vh;
  overflow-x: hidden;
}

/* Subtle animated gradient background */
body::before {
  content: '';
  position: fixed;
  top: -50%; left: -50%;
  width: 200%; height: 200%;
  background: radial-gradient(ellipse at 30% 20%, rgba(56,189,248,0.06) 0%, transparent 50%),
              radial-gradient(ellipse at 70% 80%, rgba(52,211,153,0.04) 0%, transparent 50%),
              radial-gradient(ellipse at 50% 50%, rgba(99,102,241,0.03) 0%, transparent 60%);
  animation: bgDrift 20s ease-in-out infinite alternate;
  z-index: -1;
  pointer-events: none;
}

@keyframes bgDrift {
  0% { transform: translate(0, 0) rotate(0deg); }
  100% { transform: translate(-3%, -2%) rotate(3deg); }
}

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 0 0 var(--accent-glow); }
  50% { box-shadow: 0 0 20px 4px var(--accent-glow); }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes nodeAppear {
  from { opacity: 0; transform: scale(0.85); }
  to { opacity: 1; transform: scale(1); }
}

.container {
  display: grid;
  grid-template-columns: 1fr 500px;
  gap: 24px;
  max-width: 1320px;
  margin: 0 auto;
  animation: fadeSlideUp 0.5s ease-out;
}

.panel {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 26px;
  position: relative;
  overflow: hidden;
}

/* Subtle top-edge glow on panels */
.panel::before {
  content: '';
  position: absolute;
  top: 0; left: 10%; right: 10%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0.4;
}

.header-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 6px;
}

h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
  background: linear-gradient(135deg, var(--text) 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.mode-badge {
  font-size: 11px;
  padding: 3px 12px;
  border-radius: 99px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  transition: all 0.3s ease;
}
.mode-real {
  background: rgba(52,211,153,0.15);
  color: var(--green);
  border: 1px solid rgba(52,211,153,0.3);
}
.mode-demo {
  background: rgba(251,191,36,0.12);
  color: var(--amber);
  border: 1px solid rgba(251,191,36,0.25);
}

/* ── Toggle ── */
.toggle-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 14px 0 18px;
}
.toggle-label {
  font-size: 14px;
  color: var(--text-muted);
  transition: color 0.3s;
}
.switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 26px;
  flex-shrink: 0;
}
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background: #1a2540;
  border-radius: 26px;
  transition: all 0.3s ease;
  border: 1px solid var(--border);
}
.slider::before {
  content: '';
  position: absolute;
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 2px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: all 0.3s ease;
}
input:checked + .slider {
  background: rgba(52,211,153,0.2);
  border-color: rgba(52,211,153,0.4);
}
input:checked + .slider::before {
  transform: translateX(22px);
  background: var(--green);
  box-shadow: 0 0 8px var(--green-glow);
}

/* ── Input & Buttons ── */
textarea {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 10px;
  padding: 14px 16px;
  font-family: inherit;
  font-size: 15px;
  resize: vertical;
  line-height: 1.5;
  transition: border-color 0.2s;
}
textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.btn-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 16px 0;
}

button {
  border: 0;
  padding: 12px 24px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  overflow: hidden;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, #38bdf8, #6366f1);
  color: #fff;
  box-shadow: 0 4px 15px rgba(56,189,248,0.25);
}
.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(56,189,248,0.35);
}
.btn-primary:active:not(:disabled) {
  transform: translateY(0);
}

.btn-stop {
  background: #1a2540;
  color: var(--text-muted);
  border: 1px solid var(--border);
}
.btn-stop:hover:not(:disabled) {
  border-color: var(--red);
  color: var(--red);
}

.status-text {
  font-size: 14px;
  color: var(--text-muted);
  margin-left: 4px;
}

/* ── Output ── */
#out {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px;
  white-space: pre-wrap;
  min-height: 260px;
  max-height: 420px;
  overflow-y: auto;
  font-size: 15px;
  line-height: 1.65;
  color: #c8d3e6;
  scrollbar-width: thin;
  scrollbar-color: #1a2540 transparent;
}
#out::-webkit-scrollbar { width: 6px; }
#out::-webkit-scrollbar-track { background: transparent; }
#out::-webkit-scrollbar-thumb { background: #1a2540; border-radius: 3px; }

/* ── Info Chips ── */
.info-bar {
  display: flex;
  gap: 14px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.info-chip {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
  animation: nodeAppear 0.3s ease-out backwards;
}
.info-chip .val {
  color: var(--text);
  font-weight: 700;
  font-size: 16px;
  min-width: 28px;
  text-align: right;
}

/* ── HITL ── */
.hitl-box {
  margin-top: 16px;
  padding: 18px 20px;
  background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(56,189,248,0.05));
  border: 1px solid rgba(99,102,241,0.25);
  border-radius: 12px;
  font-size: 15px;
  animation: fadeSlideUp 0.3s ease-out;
}
.hitl-box strong { color: var(--accent); }

.btn-approve {
  background: linear-gradient(135deg, #34d399, #059669);
  color: #052e16;
  margin-top: 10px;
  margin-right: 8px;
}
.btn-reject {
  background: linear-gradient(135deg, #f87171, #dc2626);
  color: #3f1f1f;
  margin-top: 10px;
}

/* ── Right Panel ── */
h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 14px;
}

#graph {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  min-height: 360px;
  font-size: 14px;
  transition: border-color 0.3s;
}
#graph.active {
  border-color: var(--border-glow);
  box-shadow: 0 0 20px rgba(56,189,248,0.05);
}

#path {
  font-size: 14px;
  color: var(--text-muted);
  margin-top: 12px;
  line-height: 1.6;
}
#path strong { color: var(--text); }

#graph-log {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 8px;
  max-height: 85px;
  overflow-y: auto;
  white-space: pre-line;
  line-height: 1.5;
  scrollbar-width: thin;
  scrollbar-color: #1a2540 transparent;
}

a {
  color: var(--accent);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}
a:hover { color: #7dd3fc; text-decoration: underline; }

.expected-path {
  margin-top: 12px;
  font-size: 13px;
  color: #4a5578;
  line-height: 1.5;
}
</style>
</head>
<body>
<div class="container">
  <!-- LEFT -->
  <div>
    <div class="panel">
      <div class="header-row">
        <h1>AEGIS v0.4.0</h1>
        <span id="mode-badge" class="mode-badge mode-demo">checking...</span>
      </div>
      <div class="toggle-row">
        <span class="toggle-label">Demo</span>
        <label class="switch">
          <input type="checkbox" id="demo-toggle">
          <span class="slider"></span>
        </label>
        <span class="toggle-label" id="toggle-text">Live inference</span>
      </div>
      <textarea id="inp" rows="3">Investigate checkout latency spike in us-east.</textarea>
      <div class="btn-row">
        <button class="btn-primary" id="run">Run AEGIS</button>
        <button class="btn-stop" id="stop" disabled>Stop</button>
        <span class="status-text" id="status"></span>
      </div>
      <pre id="out">Output will appear here...</pre>
      <div class="info-bar">
        <div class="info-chip" style="animation-delay:0s"><span>Steps</span> <span class="val" id="info-steps">0</span></div>
        <div class="info-chip" style="animation-delay:0.05s"><span>Confidence</span> <span class="val" id="info-conf">&mdash;</span></div>
        <div class="info-chip" style="animation-delay:0.1s"><span>Artifacts</span> <span class="val" id="info-arts">0</span></div>
        <div class="info-chip" style="animation-delay:0.15s"><span>Time</span> <span class="val" id="info-time">&mdash;</span></div>
      </div>
    </div>

    <div id="hitl-panel" class="hitl-box" style="display:none">
      <strong>HITL:</strong> Approve code changes &amp; remediation?<br>
      <button class="btn-approve" id="btn-approve" onclick="approveHITL(true)">Approve</button>
      <button class="btn-reject" id="btn-reject" onclick="approveHITL(false)">Reject</button>
      <span class="status-text" id="hitl-status"></span>
    </div>
  </div>

  <!-- RIGHT -->
  <div class="panel">
    <h3>Live LangGraph Visualizer</h3>
    <div id="graph"></div>
    <div id="path"></div>
    <div id="graph-log"></div>
    <div style="margin-top:14px">
      <a href="https://smith.langchain.com" target="_blank">View full trace in LangSmith (aegis-production) &#8599;</a>
    </div>
    <div class="expected-path">
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
let graphAvailable = false;
let isDemoMode = true;

// ── Health check ──
fetch('/health').then(r => r.json()).then(h => {
  graphAvailable = !!h.graph;
  const badge = $('#mode-badge');
  const toggle = $('#demo-toggle');
  if (graphAvailable) {
    toggle.disabled = false;
    updateToggleUI();
  } else {
    badge.textContent = 'DEMO';
    badge.className = 'mode-badge mode-demo';
    toggle.checked = false;
    toggle.disabled = true;
    $('#toggle-text').textContent = 'Live inference';
    $('#status').textContent = 'demo mode';
    out.textContent = 'AEGIS graph not loaded. Running in demo simulation mode.\n\nSet GOOGLE_API_KEY in Vercel and redeploy for live inference.';
    isDemoMode = true;
  }
}).catch(() => {
  $('#mode-badge').textContent = 'OFFLINE';
  $('#status').textContent = 'API unreachable';
});

function updateToggleUI() {
  const toggle = $('#demo-toggle');
  const badge = $('#mode-badge');
  const label = $('#toggle-text');
  isDemoMode = !toggle.checked;
  if (!graphAvailable) return;
  if (toggle.checked) {
    badge.textContent = 'LIVE';
    badge.className = 'mode-badge mode-real';
    label.textContent = 'Live inference (uses API keys)';
    $('#status').textContent = 'live mode';
  } else {
    badge.textContent = 'DEMO';
    badge.className = 'mode-badge mode-demo';
    label.textContent = 'Live inference';
    $('#status').textContent = 'demo mode';
  }
}

$('#demo-toggle').addEventListener('change', updateToggleUI);

// ── Mermaid ──
function initMermaid() {
  if (typeof mermaid !== 'undefined') {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      flowchart: { curve: 'basis', htmlLabels: true }
    });
    mermaidReady = true;
  }
}

async function renderGraph(steps) {
  const el = $('#graph');
  if (!el || !mermaidReady) {
    el.innerHTML = '<div style="padding:40px;text-align:center;color:#4a5578">Graph loading...</div>';
    return;
  }

  let m = 'graph TD\n'
    + '    supervisor[Supervisor] --> sre_analyst[SRE Analyst]\n'
    + '    supervisor --> knowledge[Knowledge]\n'
    + '    supervisor --> coder[Coder]\n'
    + '    supervisor --> evaluator[Evaluator]\n'
    + '    supervisor --> communicator[Communicator]\n'
    + '    sre_analyst --> supervisor\n'
    + '    knowledge --> supervisor\n'
    + '    coder --> supervisor\n'
    + '    evaluator --> supervisor\n'
    + '    communicator --> supervisor\n'
    + '    supervisor -->|HITL interrupt| hitl[HITL]\n'
    + '    hitl --> evaluator\n';

  m += '\nclassDef active fill:#38bdf8,stroke:#1e3a5f,stroke-width:3px,color:#0a0f1c\n'
    + 'classDef completed fill:#34d399,stroke:#065f46,stroke-width:2px,color:#052e16\n'
    + 'classDef default fill:#1a2540,stroke:#2d3a52,color:#c8d3e6\n';

  const last = steps.length ? steps[steps.length - 1] : '';
  steps.forEach((s, idx) => {
    if (s && idx < steps.length - 1) m += 'class ' + s + ' completed\n';
  });
  if (last) m += 'class ' + last + ' active\n';

  el.classList.toggle('active', steps.length > 0);

  try {
    const { svg } = await mermaid.render('mmd-' + Date.now(), m);
    el.innerHTML = svg;
  } catch (err) {
    el.innerHTML = '<div style="padding:20px;color:#f87171;font-size:13px">Mermaid render error</div>';
  }
}

function addStep(step, description) {
  if (step === 'supervisor' || step === 'hitl' || !currentPath.includes(step)) {
    currentPath.push(step);
  }
  renderGraph(currentPath);
  const pathEl = $('#path');
  if (pathEl) pathEl.innerHTML = '<strong>Current path:</strong><br>' + currentPath.join(' &#8594; ');
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
  $('#info-time').textContent = ((Date.now() - startTime) / 1000).toFixed(1) + 's';
}

// ── HITL (instant in demo mode, real in live mode) ──
async function approveHITL(approved) {
  const hitlPanel = $('#hitl-panel');
  const btnApprove = $('#btn-approve');
  const btnReject = $('#btn-reject');
  const hitlStatus = $('#hitl-status');

  btnApprove.disabled = true;
  btnReject.disabled = true;
  hitlStatus.textContent = 'sending...';

  if (isDemoMode) {
    // Instant client-side simulation — no API call
    await new Promise(r => setTimeout(r, 600));
    if (approved) {
      out.textContent += '\n\n[HITL APPROVED] Human approved code changes. Resuming graph execution...';
      hitlStatus.textContent = 'approved';
      hitlStatus.style.color = '#34d399';
      const pathEl = $('#path');
      if (pathEl) pathEl.innerHTML += ' &#8594; <span style="color:#34d399">approved</span>';
    } else {
      out.textContent += '\n\n[HITL REJECTED] Human rejected the proposed changes. Investigation stopped.';
      hitlStatus.textContent = 'rejected';
      hitlStatus.style.color = '#f87171';
      const pathEl = $('#path');
      if (pathEl) pathEl.innerHTML += ' &#8594; <span style="color:#f87171">rejected</span>';
    }
    out.scrollTop = out.scrollHeight;
    setTimeout(() => {
      hitlPanel.style.display = 'none';
      btnApprove.disabled = false;
      btnReject.disabled = false;
      hitlStatus.textContent = '';
    }, 1200);
    return;
  }

  // Live mode — use streaming resume to show evaluator/communicator output
  const msg = approved
    ? '\n\n[HITL APPROVED] Human approved code changes. Resuming graph execution...\n'
    : '\n\n[HITL REJECTED] Human rejected the proposed changes. Stopping.\n';
  out.textContent += msg;
  out.scrollTop = out.scrollHeight;

  const pathEl = $('#path');
  if (pathEl) pathEl.innerHTML += approved ? ' &#8594; <span style="color:#34d399">approved</span>' : ' &#8594; <span style="color:#f87171">rejected</span>';

  if (!approved) {
    hitlStatus.textContent = 'rejected';
    hitlStatus.style.color = '#f87171';
    setTimeout(() => {
      hitlPanel.style.display = 'none';
      btnApprove.disabled = false;
      btnReject.disabled = false;
      hitlStatus.textContent = '';
    }, 1200);
    return;
  }

  // Stream the remaining nodes (evaluator → communicator) via SSE
  try {
    const res = await fetch('/threads/' + encodeURIComponent(lastThread) + '/resume/stream', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({approved: true, comment: 'approved via UI'})
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
    hitlStatus.textContent = 'resumed OK';
    hitlStatus.style.color = '#34d399';
  } catch (e) {
    hitlStatus.textContent = 'API error: ' + e;
    hitlStatus.style.color = '#f87171';
  }
  setTimeout(() => {
    hitlPanel.style.display = 'none';
    btnApprove.disabled = false;
    btnReject.disabled = false;
    hitlStatus.textContent = '';
  }, 1500);
}

// ── Main stream runner ──
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
      body: JSON.stringify({input: task, thread_id: lastThread, force_demo: isDemoMode}),
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
$('#stop').onclick = () => { if (controller) controller.abort(); };

window.onload = () => {
  initMermaid();
  setTimeout(() => {
    renderGraph([]);
    const pathEl = $('#path');
    if (pathEl) pathEl.innerHTML = '<em style="color:#4a5578">Graph will animate live during run</em>';
  }, 80);
};
</script>
</body>
</html>"""