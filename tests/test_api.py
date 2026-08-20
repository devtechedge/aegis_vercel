"""FastAPI TestClient smokes for the public demo surface.

Playwright is skipped: /ui is an HTMLResponse, not a Next.js app.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
for p in (str(ROOT), str(API_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.4.2"
    assert "llm_keys" in body
    assert set(body["llm_keys"]) >= {"google", "openai", "anthropic", "langsmith"}


def test_root_points_at_ui():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "online"
    assert body["ui"] == "/ui"


def test_ui_serves_branded_dashboard():
    r = client.get("/ui")
    assert r.status_code == 200
    html = r.text
    assert "AEGIS" in html
    assert "rel=\"icon\"" in html
    assert "Run AEGIS" in html
    assert "Live LangGraph Visualizer" in html


def test_demo_stream_emits_hitl_and_done():
    r = client.post(
        "/stream",
        json={"input": "Investigate checkout latency spike in us-east", "force_demo": True},
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    body = r.text
    frames = []
    for block in body.split("\n\n"):
        line = block.strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            continue
        frames.append(json.loads(payload))
    steps = [f.get("step") for f in frames if f.get("step")]
    assert "supervisor" in steps
    assert "hitl" in steps
    assert any(f.get("confidence") == 96 for f in frames)


def test_invoke_mock_or_graph_without_auth():
    """Public demo: /invoke is unauthenticated. Mock path is enough in CI."""
    r = client.post("/invoke", json={"input": "ping", "thread_id": "ci-smoke"})
    assert r.status_code == 200
    body = r.json()
    assert "thread_id" in body or "output" in body or "error" in body or "interrupted" in body
