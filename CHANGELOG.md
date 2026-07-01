# Changelog

All notable changes to AEGIS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

\---

## \[0.4.2] - 2026-07-01

### Fixed

* **Deduplicate streaming output** — content-hash dedup in `\_real\_event\_gen()` prevents identical agent output from appearing when the graph revisits a node
* **Stop metadata leakage** — `Route` and `Plan` fields now only display on the Supervisor node, preventing sub-agent nodes from showing the supervisor's routing state
* **Smart post-HITL resume** — `/threads/{id}/resume/stream` now accepts the list of already-completed nodes from the frontend and only simulates the missing evaluator/communicator output, eliminating duplicate nodes after HITL approval
* **Vercel serverless compatibility** — replaced `Command(resume=...)` with a checkpoint-aware simulation on the resume endpoint, working around in-memory LangGraph checkpoint loss between Vercel function invocations

## \[0.4.1] - 2026-07-01

### Fixed

* **Version-agnostic chunk handling** — `\_normalize\_chunk()` now detects and handles all three LangGraph `astream("updates")` return formats at runtime (bare dict, `(mode, dict)` tuple, and `(node, dict)` tuple), fixing `\[not enough values to unpack (expected 2, got 1)]` errors across different LangGraph versions
* **LangSmith link** — corrected broken `/projects/aegis-production` link to `https://smith.langchain.com`

## \[0.4.0] - 2026-07-01

### Added

* **Complete UI redesign** — dark animated gradient background, glow effects, panel top-edge accents, fade-slide-up animations
* **Demo / Live toggle** — switch between instant demo simulation and real LangGraph inference; demo mode when graph not loaded or toggle off, live mode when toggle on and graph loaded
* **Instant demo HITL** — demo mode approves/rejects in 600ms client-side instead of calling the real resume API
* **Info chips** — real-time step count, confidence %, artifact count, and elapsed timer
* **Mermaid graph visualizer** — live node highlighting with active/completed/default states, animated during execution

### Fixed

* **Toggle inversion** — fixed unchecked=demo (left) / checked=live (right); was previously inverted
* **HITL approval 75s delay in demo** — stopped demo mode from calling the real `/resume` endpoint

## \[0.3.2] - 2026-07-01

### Changed

* Bumped UI font sizes for better readability

### Fixed

* Demo simulation now populates confidence and artifact counts at completion

## \[0.3.1] - 2026-07-01

### Fixed

* Corrected `astream` tuple unpacking for the specific LangGraph version deployed on Vercel
* Fixed LangSmith trace link

## \[0.3.0] - 2026-07-01

### Added

* **Real graph streaming** — `/stream` endpoint now connects to the live LangGraph supervisor via `astream(stream\_mode="updates")`
* **HITL resume endpoint** — `POST /threads/{id}/resume` for continuing after `interrupt()` gates
* **Run info panel** — step counter, confidence display, and artifact counter in the UI
* **SSE streaming** — all inference flows use `text/event-stream` for real-time output

### Changed

* UI output area upgraded from static text to streaming pre-formatted block

## \[0.2.0] - 2026-06-30

### Added

* **LangGraph Supervisor GA** — supervisor + 6 specialist subgraphs (SRE Analyst, Knowledge, Researcher, Coder, Communicator, Evaluator)
* **14 production tools** — Tavily, Code Executor, Postgres, GitHub, Slack, Browser, Prometheus, Runbook, Arxiv, Wikipedia, Email, Calendar, FS, Memory
* **Hybrid RAG** — MultiQuery → Cohere Rerank → LLM Grader → HyDE, PGVector + BM25
* **7 agentic loops** — Perception-Plan-Act-Reflect, Supervisor-Worker, RAG Self-Correction, ReAct, HITL, Eval-Driven, Memory Consolidation
* **LangGraph Studio** support via `langgraph dev`
* **Docker Compose** infrastructure (Postgres, PGVector, Redis)
* **CI** with eval gating (faithfulness > 0.82)
* **LangServe** `/invoke` and `/docs` endpoints
* **MIT License**

