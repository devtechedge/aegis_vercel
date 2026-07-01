# AEGIS — Autonomous Enterprise Graph Intelligence System

**A self-hosted, auditable alternative to Glean + Devin + PagerDuty Autopilot, built 100% on LangChain.**

> \*\*Try it live:\*\* \[aegis-api-two.vercel.app/ui](https://aegis-api-two.vercel.app/ui) — toggle between Demo and Live inference, watch the LangGraph supervisor route specialists in real time, and approve/reject HITL gates.

AEGIS takes a natural language operational request — *"Why is checkout latency spiking in us-east?"* — and autonomously plans, delegates to specialist sub-agents, retrieves from hybrid knowledge bases, executes tools, hits human-in-the-loop gates, and posts a fully traced, evaluated, and auditable result.

[!\[CI](https://img.shields.io/github/actions/workflow/status/devtechedge/aegis\_vercel/ci.yml?branch=main)](https://github.com/devtechedge/aegis_vercel/actions)
\[!\[Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
\[!\[License: MIT](https://img.shields.io/badge/License-MIT-green.svg)]()
\[!\[LangChain](https://img.shields.io/badge/LangChain-0.3-orange)]()

\---

## Live Demo

Open [aegis-api-two.vercel.app/ui](https://aegis-api-two.vercel.app/ui) and click **Run AEGIS**.

**What you'll see:**

* **Real-time Mermaid graph** animating the execution path: Supervisor → SRE Analyst → Knowledge → Coder → \[HITL] → Evaluator → Communicator
* **Streaming agent output** — each specialist's findings appear as they execute, with confidence scores and artifact counts
* **Human-in-the-Loop gate** — the Coder produces a patch, pauses for your approval, then the Evaluator and Communicator complete the flow
* **Demo / Live toggle** — Demo mode runs an instant simulation; Live mode connects to the real LangGraph with your API keys
* **Live info panel** — step count, confidence %, artifact count, and elapsed time update in real time
* **LangSmith traces** — one-click link to the full trace for every run

### UI Screenshots

The `/ui` endpoint serves a single-page dashboard with:

* Left panel: task input, Run/Stop controls, scrolling agent output, info chips
* Right panel: animated Mermaid graph, execution path log, LangSmith link
* HITL approval panel slides in when the Coder requests human review

\---

## Architecture

```
\[Next.js UI / LangGraph Studio] <-SSE-> \[LangServe FastAPI /api]
                                        |
                              \[LangGraph Supervisor]
                   /     |      |       |       |      \\
            Researcher Coder  SRE   Knowledge Comm  Evaluator
               |         |     |        |
         Tavily/Arxiv  E2B  Prometheus  PGVector Hybrid RAG
                                        |
                                \[Postgres + PGVector + Redis]
                                        |
                              \[LangSmith Traces / Evals / Prompt Hub]
```

## Feature Matrix — Full LangChain Ecosystem

|Product|Used For|
|-|-|
|**langchain-core**|LCEL everywhere, structured output Pydantic v2, fallback LLM router|
|**langgraph**|Supervisor + 6 subgraphs, PostgresSaver, `interrupt()` HITL, `astream\_events`|
|**langsmith**|Tracing, Prompt Hub (`aegis/supervisor\_router`), Evals, Feedback API|
|**langserve**|FastAPI `/invoke`, `/stream`, `/threads/{id}/resume`, OpenAPI playground|
|**RAG**|MultiQuery → Cohere Rerank → LLM Grader → HyDE, PGVector + BM25 hybrid|
|**Tools (14)**|Tavily, Code Executor, Postgres, GitHub, Slack, Browser, Prometheus, Runbook, Arxiv, Wikipedia, Email, Calendar, FS, Memory|

## 7 Agentic Loops — All Implemented

1. Perception-Plan-Act-Reflect
2. Supervisor-Worker Hierarchical
3. RAG Self-Correction
4. Tool-Use ReAct + Self-Heal
5. Human-in-the-Loop Interrupt
6. Evaluation-Driven Self-Improvement
7. Memory Consolidation

All visible in LangSmith with custom metadata.

\---

## Quickstart

### Vercel (recommended — zero config)

1. Fork this repo
2. Import into [Vercel](https://vercel.com)
3. Set root directory to `apps/api`
4. Add `GOOGLE\_API\_KEY` (or `OPENAI\_API\_KEY`) as an environment variable
5. Deploy — visit `/ui` for the live dashboard, `/docs` for the API playground

Without API keys the UI gracefully falls back to **Demo mode** (instant simulation).

### Docker (local / self-hosted)

```bash
cp .env.example .env
docker-compose -f infra/docker-compose.yml up --build
```

* Dashboard: http://localhost:8000/ui
* API playground: http://localhost:8000/docs
* LangGraph Studio: `langgraph dev`

### API Endpoints

|Endpoint|Method|Purpose|
|-|-|-|
|`/ui`|GET|Live dashboard (SSE, Mermaid, HITL)|
|`/stream`|POST|Streaming inference (SSE)|
|`/invoke`|POST|Single-shot inference (JSON)|
|`/threads/{id}/resume`|POST|Resume after HITL (JSON)|
|`/threads/{id}/resume/stream`|POST|Resume after HITL (SSE)|
|`/health`|GET|Graph status, key availability|
|`/docs`|GET|OpenAPI / Swagger playground|

\---

## Why This Proves Senior+ AI Engineering

* **Agentic Loops**: 7 explicit loops, not chains
* **LangGraph HITL**: `interrupt()` / `Command(resume=...)`, PostgresSaver
* **LangSmith Evals/Prompt Hub**: 3 datasets, LLM-as-judge, CI gating faithfulness > 0.82
* **Hybrid RAG**: MultiQuery + Compression + Grader + HyDE
* **Multi-agent Supervisor**: 6 specialists, tool-use ReAct
* **Production Observability**: OpenTelemetry → LangSmith, run metadata
* **Vercel Serverless**: graceful degradation, SSE streaming, version-agnostic chunk handling

## Repo Structure

```
aegis/
├── apps/api/              # LangServe FastAPI + live UI
├── packages/aegis\_graph/  # Supervisor + 6 subgraphs
├── packages/tools/        # 14 production tools
├── packages/rag/          # Ingestion / retriever / vectorstore
├── packages/memory/
├── packages/evals/
├── infra/docker-compose.yml
├── tests/
└── scripts/run\_evals.py
```

## Evals

```bash
python scripts/run\_evals.py
```

Generates `evals/reports/latest.md`. CI fails if faithfulness < 0.82.

## Environment Variables

|Var|Purpose|
|-|-|
|`GOOGLE\_API\_KEY`|Gemini LLM (primary)|
|`OPENAI\_API\_KEY`|OpenAI fallback|
|`ANTHROPIC\_API\_KEY`|Coding fallback|
|`LANGCHAIN\_API\_KEY`|LangSmith tracing|
|`LANGCHAIN\_TRACING\_V2=true`|Enable tracing|
|`DATABASE\_URL`|Postgres + PGVector|
|`REDIS\_URL`|Short-term memory|
|`TAVILY\_API\_KEY`|Web search|

All optional — fake models/fallbacks keep Vercel deploy green even without keys.

\---

MIT License — Built with LangChain, LangGraph, LangSmith

