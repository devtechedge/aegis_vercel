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
    assert body["version"] == "0.9.3"
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
    assert 'id="graph-hub"' in html
    assert "graph-pill" in html
    assert "Communicator" in html
    assert "SRE Analyst" in html
    assert "sample" in html.lower() or "Investigate checkout" in html
    assert "data-theme" in html
    assert "theme-toggle" in html
    assert "aegis-theme" in html
    assert "scrollbar-color" in html
    assert "prefers-reduced-motion" in html
    assert "HITL:" in html
    assert 'id="demo-toggle"' in html
    assert "IBM Plex" in html
    assert "out-empty" in html
    assert 'id="roster"' in html
    assert "Specialists" in html
    assert "side-head" in html
    assert "flex-direction:column" in html
    assert "minmax(380px" in html
    assert "graph-fan" in html


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


def test_debug_gated_by_default():
    r = client.get("/debug")
    assert r.status_code == 404


def test_health_reports_live_mode_flag():
    r = client.get("/health")
    assert r.status_code == 200
    assert "live_mode" in r.json()
    assert r.json()["live_mode"] is False


def test_live_mode_on_when_key_present(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("LIVE_MODE", raising=False)
    r = client.get("/health")
    assert r.json()["live_mode"] is True


def test_live_mode_off_when_explicitly_disabled(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("LIVE_MODE", "false")
    r = client.get("/health")
    assert r.json()["live_mode"] is False


def test_ui_sets_security_headers():
    r = client.get("/ui")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
