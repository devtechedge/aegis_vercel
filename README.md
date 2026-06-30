# AEGIS — Autonomous Enterprise Graph Intelligence System

**A self-hosted, auditable alternative to Glean + Devin + PagerDuty Autopilot, built 100% on LangChain.**

AEGIS takes a natural language operational request: _"Why is checkout latency spiking in us-east? Check recent deploys, run a runbook, summarize related Slack threads, and open a PR with a fix if safe."_

It then autonomously plans, delegates to specialist sub-agents, retrieves from hybrid knowledge bases, executes tools, hits human-in-the-loop gates, and posts a fully traced, evaluated, and auditable result.

[![CI](https://img.shields.io/github/actions/workflow/status/devtechedge/aegis_vercel/ci.yml?branch=main)](https://github.com/devtechedge/aegis_vercel/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)]()
[![LangChain](https://img.shields.io/badge/LangChain-0.3-orange)]()

Live: https://aegis-api-two.vercel.app — Docs: https://aegis-api-two.vercel.app/docs

---

## Architecture

```
[Next.js UI / LangGraph Studio] <-SSE-> [LangServe FastAPI /api]
                                        |
                              [LangGraph Supervisor]
                   /     |      |       |       |      \
            Researcher Coder  SRE   Knowledge Comm  Evaluator
               |         |     |        |
         Tavily/Arxiv  E2B  Prometheus  PGVector Hybrid RAG
                                        |
                                [Postgres + PGVector + Redis]
                                        |
                              [LangSmith Traces / Evals / Prompt Hub]
```

## Feature Matrix – Full LangChain Ecosystem

| Product | Used For |
|---|---|
| **langchain-core** | LCEL everywhere, structured output Pydantic v2, fallback LLM router |
| **langgraph** | Supervisor + 6 subgraphs, PostgresSaver, `interrupt()` HITL, `astream_events` |
| **langsmith** | Tracing, Prompt Hub (`aegis/supervisor_router`), Evals, Feedback API |
| **langserve** | FastAPI `/invoke`, `/stream`, `/threads/{id}/resume`, OpenAPI playground |
| **RAG** | MultiQuery → Cohere Rerank → LLM Grader → HyDE, PGVector + BM25 hybrid |
| **Tools (14)** | Tavily, Code Executor, Postgres, GitHub, Slack, Browser, Prometheus, Runbook, Arxiv, Wikipedia, Email, Calendar, FS, Memory |

## 7 Agentic Loops – All Implemented

1. Perception-Plan-Act-Reflect
2. Supervisor-Worker Hierarchical
3. RAG Self-Correction
4. Tool-Use ReAct + Self-Heal
5. Human-in-the-Loop Interrupt
6. Evaluation-Driven Self-Improvement
7. Memory Consolidation

All visible in LangSmith with custom metadata.

## Quickstart

```bash
cp .env.example .env
docker-compose -f infra/docker-compose.yml up --build
```

- API: http://localhost:8000/docs
- Playground: http://localhost:8000/aegis/playground
- Web UI: http://localhost:3000 (coming soon)

Vercel: Root Directory = `apps/api`, works serverless with graceful fallbacks.

### Invoke

```bash
curl -X POST http://localhost:8000/invoke \
  -H "content-type: application/json" \
  -d '{"input":"Investigate checkout latency spike in us-east","thread_id":"inc-342"}'
```

Streaming SSE: `POST /stream`

HITL Resume:
```bash
curl -X POST http://localhost:8000/threads/inc-342/resume \
  -d '{"approved": true}'
```

## Why this proves Senior+ AI Engineering

- **Agentic Loops**: 7 explicit loops, not chains
- **LangGraph HITL**: `interrupt()` / `Command(resume=...)`, PostgresSaver
- **LangSmith Evals/Prompt Hub**: 3 datasets, LLM-as-judge, CI gating faithfulness >0.82
- **Hybrid RAG**: MultiQuery + Compression + Grader + HyDE
- **Multi-agent Supervisor**: 6 specialists, tool-use ReAct
- **Production Observability**: OpenTelemetry → LangSmith, run metadata

## Repo Structure

```
aegis/
├── apps/api/              # LangServe FastAPI
├── packages/aegis_graph/  # Supervisor + 6 subgraphs
├── packages/tools/        # 14 production tools
├── packages/rag/          # Ingestion / retriever / vectorstore
├── packages/memory/
├── packages/evals/
├── infra/docker-compose.yml
├── tests/
└── scripts/run_evals.py
```

## Evals

```bash
python scripts/run_evals.py
```

Generates `evals/reports/latest.md`. CI fails if faithfulness < 0.82.

## Environment Variables

| Var | Purpose |
|---|---|
| `OPENAI_API_KEY` | Core LLM |
| `ANTHROPIC_API_KEY` | Coding fallback |
| `LANGCHAIN_API_KEY` | LangSmith tracing |
| `LANGCHAIN_TRACING_V2=true` | Enable tracing |
| `DATABASE_URL` | Postgres + PGVector |
| `REDIS_URL` | Short-term memory |
| `TAVILY_API_KEY` | Web search |

All optional – fake models/fallbacks keep Vercel deploy green.

## Demo for Recruiters

1. Open https://aegis-api-two.vercel.app/docs
2. POST `/invoke` with: `"Investigate checkout latency spike in us-east. Check recent deploys, run a runbook, summarize Slack threads."`
3. See Supervisor → SRE Analyst → Knowledge RAG → Coder → Evaluator → Communicator trace in LangSmith
4. RAG grader loop visible, HITL interrupt for PR creation
5. `POST /threads/{id}/resume {"approved":true}` continues
6. Streaming works at `/stream`

Local: `docker-compose up`, open LangGraph Studio: `langgraph dev`

---

MIT License — Built with LangChain, LangGraph, LangSmith
