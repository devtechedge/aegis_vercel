"""Demo-hardening helpers for the public AEGIS FastAPI surface.

In-memory rate limits reset per serverless instance - residual, documented in SECURITY.md.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Header, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

DEFAULT_CORS = [
    "https://aegis-agent-api.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    ),
}


def cors_origins() -> list[str]:
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if not raw:
        return list(DEFAULT_CORS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def debug_enabled() -> bool:
    return os.getenv("ENABLE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def live_mode_enabled() -> bool:
    """Live LLM path when an LLM key is present, unless LIVE_MODE is explicitly off."""
    keys = ("GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    if not any(bool(os.getenv(k)) for k in keys):
        return False
    raw = os.getenv("LIVE_MODE")
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def public_run_token() -> str | None:
    tok = (os.getenv("PUBLIC_RUN_TOKEN") or "").strip()
    return tok or None


def require_run_token_if_configured(
    x_run_token: str | None = Header(default=None, alias="x-run-token"),
) -> None:
    """When LIVE_MODE and PUBLIC_RUN_TOKEN are set, require matching x-run-token."""
    if not live_mode_enabled():
        return
    expected = public_run_token()
    if not expected:
        return
    if not x_run_token or x_run_token != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid x-run-token")


class InMemoryRateLimiter:
    """Sliding-window per-IP limiter (best-effort on serverless)."""

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self._hits[key]
        cutoff = now - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.max_requests:
            raise HTTPException(status_code=429, detail="Rate limit exceeded; retry shortly")
        q.append(now)


# Shared limiter for invoke / stream / resume
invoke_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60.0)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def rate_limit_invoke(request: Request) -> None:
    invoke_limiter.check(client_ip(request))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path or ""
        if path == "/ui" or path.startswith("/ui/"):
            for k, v in SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
        else:
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
