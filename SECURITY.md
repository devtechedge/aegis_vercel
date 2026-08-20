# Security Assessment — AEGIS (aegis_vercel)

**Date:** 2026-08-21  
**Scope:** Auth, XSS, injection, CORS, secrets, tool execution, HITL, evals  
**Context:** Public deploy is a **portfolio demo** of a LangGraph supervisor + 6 specialists. Live UI: [aegis-agent-api.vercel.app/ui](https://aegis-agent-api.vercel.app/ui). Vercel project `aegis-api`, Root Directory `apps/api`.

---

## Executive summary

| Area | Risk | Notes |
|------|------|--------|
| Authentication | **None (accepted)** | `/invoke`, `/stream`, `/threads/{id}/resume` are public. No API key, JWT, or session. |
| Authorization | **None (accepted)** | HITL “approve” is an unauthenticated POST. Anyone who can hit the URL can resume a thread. |
| XSS | **Low (demo UI)** | `/ui` is a server-rendered HTMLResponse. User task text is written into the output pane via `textContent` (escaped). Mermaid SVG is rendered from a fixed template, not from raw user HTML. |
| Injection (SQL) | **Low** | Live Vercel path mocks SQL. Write verbs (`INSERT`/`UPDATE`/`DELETE`/`DROP`/`ALTER`) return `WRITE_BLOCKED`. |
| Code execution | **Demo residual** | `code_executor` runs restricted `exec()` with a tiny `__builtins__` allow-list. Not a production sandbox (not E2B / gVisor). |
| CORS | **Demo residual** | `allow_origins=["*"]` with `allow_credentials=True` (spec-invalid combo; browsers ignore credentials on `*`). Dashboard is same-origin so CORS rarely applies. |
| Secrets in repo | **Low** | `.env` gitignored. `.env.example` has empty placeholders only. |
| Payments / PII | **N/A** | No payments, no user accounts, no PII store. |
| Eval gate | **Honest mock** | Public CI has no `LANGCHAIN_API_KEY`. `scripts/run_evals.py` writes a **mock** faithfulness report. Do not read CI “≥ 0.82” as a live LangSmith score. |

**Overall (public Vercel demo):** Low residual risk for a recruiter demo — mock tools, no user data, same-origin dashboard.

**Overall (if this were an internal ops copilot with live GitHub / Slack / SQL / email):** High — unauthenticated invoke + HITL resume, restricted-but-real `exec`, CORS `*`. Do **not** claim production auth, JWT, or a hardened code sandbox.

---

## 1. Authentication

**Findings**
- FastAPI app in `apps/api/main.py` has no `Depends`, no bearer header, no cookie session.
- `/health` reports whether LLM keys are *present* (booleans only — not the secret values).
- `/debug` exposes Python version and cwd. Fine for a demo; strip it before any private deploy.

**Verdict:** Unauthenticated public API. Accepted for the portfolio demo. Not accepted for a company-internal agent that can open PRs or send Slack.

**If auth is added later:** edge middleware or FastAPI dependency (API key or OIDC), rate-limit `/invoke` and `/stream`, drop `/debug` from production.

---

## 2. HITL is a UX gate, not an authz boundary

LangGraph `interrupt()` / `Command(resume=...)` pauses the graph. On Vercel, in-memory `MemorySaver` checkpoints do not survive the next serverless invocation, so `/threads/{id}/resume/stream` **simulates** the post-HITL evaluator → communicator tail.

That is documented in the handler docstring. It means:

- Demo-mode Approve/Reject is client-side (no API call).
- Live-mode resume is an unauthenticated POST. Thread IDs are guessable (`web-<timestamp>`).
- Tool-level `HITL_REQUIRED` strings (GitHub PR, Slack post, email) are **returned to the model**, not enforced by a human identity.

Accepted for the demo. Not a SOC2 control.

---

## 3. Tool allow-lists (what *is* enforced)

| Tool | Guard | Behaviour |
|------|--------|-----------|
| `postgres_sql_toolkit` | keyword block | Write SQL → `WRITE_BLOCKED` |
| `file_system_tool` | path block | `..` or `/etc` → `SECURITY_BLOCKED` |
| `github_toolkit` | action block | `create_pr` / `branch` → `HITL_REQUIRED` |
| `slack_toolkit` | action block | `post_message` → `HITL_REQUIRED` |
| `send_email_tool` | always | `HITL_REQUIRED` |
| `code_executor` | language + builtins | Non-Python refused; `exec` with `print`/`range`/`len`/`sum` only |

Covered by `tests/test_tool_guards.py`. These are string-level guards on mock tools, not a policy engine.

---

## 4. XSS / UI

- Dashboard lives at `/ui` (HTMLResponse), not the leftover `apps/web` Next.js stub.
- Streaming tokens append via `textContent`.
- Mermaid is initialized on a static graph template. User input is not concatenated into the mermaid source.
- Third-party script: `cdn.jsdelivr.net/npm/mermaid@10`. Residual supply-chain risk, accepted for demo.

`apps/web` still points at the retired `aegis-api-two.vercel.app` URL and is **not** the live product. Left in tree; do not treat it as a second public surface.

---

## 5. CORS

```python
allow_origins=["*"]
allow_credentials=True
```

Browsers will not send credentials with a `*` origin. Same-origin `/ui` does not need CORS. Left as-is so a recruiter can `fetch` `/stream` from another origin during a take-home clone. Tighten to the production alias if this API is ever put behind a private UI.

---

## 6. Secrets & config

- `.gitignore` excludes `.env`, `.env.local`, `.env.*.local`.
- `.env.example` documents `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LANGCHAIN_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `TAVILY_API_KEY`, `GITHUB_TOKEN`, `SLACK_BOT_TOKEN` — all empty.
- Vercel env holds the live Google + LangSmith keys. They are not in git.
- `/health` only returns booleans for key presence.

Never commit `LANGCHAIN_API_KEY`, LLM keys, or database passwords.

---

## 7. HTTP surface (demo)

| Path | Auth | Notes |
|------|------|--------|
| `/` | None | Status JSON |
| `/health` | None | Graph + key-presence booleans |
| `/debug` | None | Python version / cwd — demo only |
| `/ui` | None | Live dashboard |
| `/docs` | None | OpenAPI playground |
| `POST /invoke` | None | Runs the graph or returns mock |
| `POST /stream` | None | SSE; `force_demo=true` is the recruiter path |
| `POST /threads/{id}/resume` | None | HITL resume |
| `POST /threads/{id}/resume/stream` | None | Post-HITL SSE simulation (Vercel) |
| `/fleet/*` | None | Stub list of bots |

---

## 8. Dependencies / supply chain

- Vercel installs `apps/api/requirements-vercel.txt` (slim, no FAISS / pgvector / redis).
- Full local stack is `apps/api/requirements.txt`.
- Ranges are `>=` (LangChain / LangGraph move fast). **Do not** over-pin to clear an advisory; majors are Dependabot-ignored.
- `pip-audit` runs in CI with `continue-on-error: true`. A FastAPI/LangChain major CVE is not a CI-red reason to jump a major.
- Duplicate `packages/` vs `apps/api/packages/` is the Vercel bundling path (Root Directory cannot see repo-root packages). Keep both.

---

## 9. Eval honesty

README historically said “CI fails if faithfulness < 0.82”. Public GitHub Actions does **not** have `LANGCHAIN_API_KEY`, so `scripts/run_evals.py` writes a canned markdown table and exits 0.

Live LangSmith project: `aegis-production`. Real faithfulness is visible there when keys are set, not on the public CI badge.

---

## 10. Residual risk & acceptance

**Accepted for portfolio demo**
- No authentication on invoke / stream / HITL resume.
- CORS `*`.
- Restricted `exec` in `code_executor`.
- Mock SQL / GitHub / Slack / FS tools on Vercel.
- Mock eval report in public CI.
- Leftover unused `apps/web` Next.js stub.

**Not accepted if this becomes an internal production copilot**
- Unauthenticated `/invoke` that can reach live tools.
- HITL resume without an identity.
- `exec` instead of a real sandbox.
- `/debug` on the public internet.
- Eval gate that does not actually call LangSmith.

---

## 11. How to re-test

```bash
python -m pip install -r apps/api/requirements.txt
python -m pip install pytest ruff mypy
PYTHONPATH=. pytest -q --tb=short
ruff check tests packages apps/api/packages apps/api/main.py apps/api/routers scripts
mypy packages/tools packages/evals tests --ignore-missing-imports --follow-imports=skip
PYTHONPATH=. python scripts/run_evals.py   # mock unless LANGCHAIN_API_KEY is set
```
