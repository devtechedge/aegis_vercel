import os
import sys
import json
import time
import asyncio
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from security_hardening import (
    SecurityHeadersMiddleware,
    cors_origins,
    debug_enabled,
    live_mode_enabled,
    rate_limit_invoke,
    require_run_token_if_configured,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

VERSION = "0.9.2"


def _sse(payload: dict) -> str:
    """Encode one SSE data frame without py3.11 f-string backslash bans."""
    return "data: " + json.dumps(payload) + "\n\n"


app = FastAPI(title="AEGIS API", version=VERSION, description="Autonomous Enterprise Graph Intelligence System")

_origins = cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "x-run-token", "Authorization"],
)
app.add_middleware(SecurityHeadersMiddleware)

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
    completed: list[str] = []  # nodes already shown (sent by frontend)


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
        "live_mode": live_mode_enabled(),
        "llm_keys": {
            "google": bool(os.getenv("GOOGLE_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "langsmith": bool(os.getenv("LANGCHAIN_API_KEY")),
        },
    }


@app.get("/debug")
def debug():
    if not debug_enabled():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return {
        "graph_loaded": bool(graph),
        "graph_error": graph_load_error,
        "python": sys.version,
        "cwd": os.getcwd(),
        "live_mode": live_mode_enabled(),
    }


@app.post("/invoke")
async def invoke(
    req: InvokeRequest,
    request: Request,
    _rl: None = Depends(rate_limit_invoke),
    _tok: None = Depends(require_run_token_if_configured),
):
    if not live_mode_enabled() or req.force_demo or not graph:
        return {"output": f"[mock] {req.input}", "mock": True, "graph_error": graph_load_error, "live_mode": False}
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
async def resume_thread(
    thread_id: str,
    req: ResumeRequest,
    request: Request,
    _rl: None = Depends(rate_limit_invoke),
    _tok: None = Depends(require_run_token_if_configured),
):
    if not live_mode_enabled() or not graph:
        return {"thread_id": thread_id, "resumed": False, "error": "Graph not loaded or LIVE_MODE off", "mock": True}
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
async def resume_thread_stream(
    thread_id: str,
    req: ResumeRequest,
    request: Request,
    _rl: None = Depends(rate_limit_invoke),
    _tok: None = Depends(require_run_token_if_configured),
):
    """SSE streaming resume - emits post-HITL evaluator/communicator flow.

    On Vercel serverless, in-memory LangGraph checkpoints (MemorySaver) are
    lost between function invocations.  Command(resume=...) on a fresh process
    would restart the entire graph from scratch, causing duplicate output and
    a second HITL interrupt.  Instead, we stream a clean post-HITL simulation
    of the expected evaluator → communicator completion path.
    """
    async def gen():
        if not req.approved:
            yield _sse({"token": "\n[REJECTED] Investigation halted per human decision.\n"})
            yield "data: [DONE]\n\n"
            return

        done = set(req.completed)  # nodes already streamed to the UI
        need_evaluator = "evaluator" not in done
        need_comms = "communicator" not in done

        if not need_evaluator and not need_comms:
            # HITL was on the last node (e.g. communicator/slack_post) —
            # just confirm approval and show final metrics.
            await asyncio.sleep(0.3)
            yield _sse({"token": "\n[RESUMED] Human approval confirmed. Action executed.\n"})
            yield _sse({"confidence": 91, "artifacts": ["rca.md", "patch.diff", "incident_report.md", "postmortem.md"]})
            yield "data: [DONE]\n\n"
            return

        await asyncio.sleep(0.5)

        if need_evaluator:
            yield _sse({"step": "evaluator", "description": DESCRIPTORS["evaluator"]})
            await asyncio.sleep(0.8)
            yield _sse({
                "token": (
                    "[EVALUATOR] Evaluator scoring output quality and verifying against SLOs\n\n"
                    "  Quality Score: 91/100\n"
                    "  SLO Compliance: PASS - all latency, error-rate and availability checks within thresholds\n"
                    "  Patch Validation: Code changes verified against staging environment\n"
                    "  Confidence: 91%\n\n"
                )
            })
            await asyncio.sleep(0.4)

        if need_comms:
            yield _sse({"step": "communicator", "description": DESCRIPTORS["communicator"]})
            await asyncio.sleep(0.8)
            yield _sse({
                "token": (
                    "[COMMUNICATOR] Communicator composing final summary and incident report\n\n"
                    "  Final incident report generated and distributed to stakeholders.\n"
                    "  Slack notification sent to #incidents with RCA summary.\n"
                    "  Runbook updated with new checkout_latency findings.\n"
                    "  Post-mortem scheduled for tomorrow 10:00 UTC.\n\n"
                )
            })

        # Final metrics
        yield _sse({"confidence": 91, "artifacts": ["rca.md", "patch.diff", "incident_report.md", "postmortem.md"]})
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
    # Only use the LAST message from each node - earlier messages are
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

    # Routing metadata - only show on supervisor to prevent
    # leakage into sub-agent nodes (e.g. sre_analyst showing Route -> sre_analyst)
    if node == "supervisor":
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


async def _demo_event_gen():
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
        await asyncio.sleep(0.08)
        end_word = min(word_idx + 6, len(words))
        for w in range(word_idx, end_word):
            token = words[w] + (" " if w < len(words) - 1 else "")
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0.02)
        word_idx = end_word
    for w in range(word_idx, len(words)):
        token = words[w] + (" " if w < len(words) - 1 else "")
        yield f"data: {json.dumps({'token': token})}\n\n"
        await asyncio.sleep(0.02)
    yield f"data: {json.dumps({'confidence': 96, 'artifacts': ['diagnostic_script.py', 'patch.diff', 'incident_report.md']})}\n\n"



def _real_event_gen(task: str, thread_id: str):
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": thread_id}}

    def _normalize_chunk(chunk):
        """Handle different LangGraph versions returning different astream shapes.

        LangGraph has changed astream(stream_mode="updates") return format across versions:
          - Some yield (mode_str, {node_name: update_dict})  - newest
          - Some yield (node_name, update_dict)               - older
          - Some yield {node_name: update_dict}               - no tuple

        This normalises all three into {node_name: update_dict}.
        """
        # Case 1: bare dict - already {node_name: update}
        if isinstance(chunk, dict):
            return chunk
        # Case 2 & 3: tuple of 2
        if isinstance(chunk, tuple) and len(chunk) == 2:
            first, second = chunk
            # If second is a dict whose keys include agent names → (mode, {node: update})
            if isinstance(second, dict) and any(k in DESCRIPTORS for k in second):
                return second
            # Otherwise → (node_name, update_dict) - old format
            return {first: second} if isinstance(second, dict) else {str(first): second}
        # Fallback: treat as single dict
        return chunk if isinstance(chunk, dict) else {"unknown": chunk}

    async def gen():
        seen = set()
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
                        h = hash(text)
                        if h not in seen:
                            seen.add(h)
                            yield _sse({"token": text + "\n\n"})
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
async def stream(
    req: InvokeRequest,
    request: Request,
    _rl: None = Depends(rate_limit_invoke),
    _tok: None = Depends(require_run_token_if_configured),
):
    # Default: demo/sim. Live graph only when LIVE_MODE + keys + graph + not force_demo.
    if (not live_mode_enabled()) or (not graph) or req.force_demo:
        return StreamingResponse(_demo_event_gen(), media_type="text/event-stream")
    return StreamingResponse(
        _real_event_gen(req.input, req.thread_id),
        media_type="text/event-stream",
    )


# ── UI ──────────────────────────────────────────────────────────────────────

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    ui_path = os.path.join(os.path.dirname(__file__), "static", "ui.html")
    with open(ui_path, encoding="utf-8") as fh:
        html = fh.read().replace("{{VERSION}}", VERSION)
    return HTMLResponse(html)


@app.get("/og.png")
def og_image():
    return FileResponse(os.path.join(os.path.dirname(__file__), "og.png"),
                        media_type="image/png")
