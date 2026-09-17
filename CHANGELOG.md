# Changelog

All notable changes to AEGIS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

---

## [0.9.4] - 2026-09-17

### Changed
- **HITL gate** — the overlay no longer dims or blurs the dashboard. The dialog docks at the bottom so Supervisor → Communicator stays visible; title/hint recede, Approve and Reject stay full-contrast.

---

## [0.9.3] - 2026-09-17

### Changed
- **Live inference** — Demo → Live is enabled whenever an LLM key is present. Set `LIVE_MODE=false` to force demo/sim. Restores the July public-demo toggle on production (Gemini key already configured).

---

## [0.9.2] - 2026-09-17

### Fixed
- **Visualizer rail** — production `/ui` still laid the LangGraph column out as a row, so the title, Idle/Live/Done legend, specialist roster, path, and LangSmith link painted on top of each other. The rail is now a column (`flex-direction: column !important`) with independent scroll.
- **Hub graph** — the circular SVG hub was wider than the rail and clipped Communicator. Specialists now sit in a two-column pill grid that shrinks with the panel, with labels that ellipsize instead of overflowing.

---

## [0.9.1] - 2026-09-17

### Fixed
- **Visualizer rail** — at desktop widths the LangGraph panel was `display: flex` in a row, which collapsed the hub and stacked the title, Idle/Live/Done legend, specialist roster, and LangSmith copy on top of each other. The rail is now a column with independent scroll, wrapping guards, and a grid roster.

---

## [0.9.0] - 2026-09-17

### Changed
- **Operations console** - IBM Plex typography, cooler titanium canvas, specialist transcript cards, and a radar-backed LangGraph hub. Same `/stream` and `/threads/{id}/resume/stream` contracts, theme toggle, overlay scrollbars, and HITL gate.

---

## [0.8.0] - 2026-09-17

### Changed
- **Operations console** - denser full-viewport layout: run HUD sits above the transcript, the visualizer shares the rail with a live specialist roster, and Demo/Live status is a persistent header pulse.
- **HITL gate** - status reads "awaiting approval" while the dialog is open instead of flipping to done mid-gate.

### Added
- Specialist roster with idle / live / done for Supervisor, SRE Analyst, Knowledge, Coder, HITL, Evaluator, and Communicator.
- Activity rail of the last graph descriptions above the stream.

---

## [0.7.0] - 2026-09-17

### Changed
- **LangGraph hub** - specialists are labeled pills with names drawn inside the node (SRE Analyst, Knowledge, Coder, HITL, Evaluator, Communicator), so the graph stays readable on a phone. HITL is a dashed gate until it fires.
- **Transcript** - stream panel has an idle / running / done hint, a caret while tokens arrive, and empty-state styling. Same SSE contract (`/stream`, `/threads/{id}/resume/stream`).
- **HITL dialog** - Tab cycles Approve / Reject while the gate is open.

### Added
- Idle / Live / Done legend under the visualizer.

---

## [0.6.0] - 2026-09-17

### Changed
- **Operations console** - spatial LangGraph hub (supervisor plus specialists) replaces the vertical stepper, with live edge highlighting as the run routes.
- **HITL gate** - approval is a focused dialog over the console instead of an inline panel, with the Approve control focused on open.
- **Mobile panes** - Console and Graph are tabbed below 960px so the visualizer is one tap away instead of below the fold.
- **Sample requests** - three starter incidents fill the request field without changing API behavior.
- **Artifact chips** - completed runs list produced files under the stream.
- **Stream status** - running state uses a reduced-motion-safe shimmer; output still streams through the same SSE contract (`/stream`, `/threads/{id}/resume/stream`).

### Added
- Dashboard tests cover the hub graph marker while keeping the v0.5.0 chrome assertions (theme toggle, overlay scrollbars, HITL copy).

---

## [0.5.0] - 2026-09-16

### Changed
- **Dashboard restyle** - cool titanium light/dark tokens, overlay hover-reveal scrollbars, and a sticky operations chrome. Removed cyan-indigo glow, animated gradient blobs, and gradient primary buttons.
- **Responsive console** - single-column stack on phones and tablets; two-column console + visualizer from 960px. Touch targets are at least 44px.
- **LangGraph visualizer** - live stepper (idle / live / done) instead of a blocking Mermaid CDN load, so first paint is no longer gated on a multi-megabyte graph library.
- **Accessibility** - skip link, labelled request field, visible focus, `aria-live` on stream and status, `prefers-reduced-motion`, keyboard Run (Ctrl/⌘+Enter) and Stop (Escape).
- **Demo stream pacing** - `/stream` demo mode yields tokens with short delays so the dashboard can animate instead of painting the full transcript in one frame.

### Added
- Dashboard HTML lives in `apps/api/static/ui.html` and is served by `/ui` with the current version substituted.

---

## [0.4.2] - 2026-07-01

### Fixed
- **Deduplicate streaming output** - content-hash dedup in `_real_event_gen()` prevents identical agent output from appearing when the graph revisits a node
- **Stop metadata leakage** - `Route` and `Plan` fields now only display on the Supervisor node, preventing sub-agent nodes from showing the supervisor's routing state
- **Smart post-HITL resume** - `/threads/{id}/resume/stream` now accepts the list of already-completed nodes from the frontend and only simulates the missing evaluator/communicator output, eliminating duplicate nodes after HITL approval
- **Vercel serverless compatibility** - replaced `Command(resume=...)` with a checkpoint-aware simulation on the resume endpoint, working around in-memory LangGraph checkpoint loss between Vercel function invocations

## [0.4.1] - 2026-07-01

### Fixed
- **Version-agnostic chunk handling** - `_normalize_chunk()` now detects and handles all three LangGraph `astream("updates")` return formats at runtime (bare dict, `(mode, dict)` tuple, and `(node, dict)` tuple), fixing `[not enough values to unpack (expected 2, got 1)]` errors across different LangGraph versions
- **LangSmith link** - corrected broken `/projects/aegis-production` link to `https://smith.langchain.com`

## [0.4.0] - 2026-07-01

### Added
- **Complete UI redesign** - dark animated gradient background, glow effects, panel top-edge accents, fade-slide-up animations
- **Demo / Live toggle** - switch between instant demo simulation and real LangGraph inference; demo mode when graph not loaded or toggle off, live mode when toggle on and graph loaded
- **Instant demo HITL** - demo mode approves/rejects in 600ms client-side instead of calling the real resume API
- **Info chips** - real-time step count, confidence %, artifact count, and elapsed timer
- **Mermaid graph visualizer** - live node highlighting with active/completed/default states, animated during execution

### Fixed
- **Toggle inversion** - fixed unchecked=demo (left) / checked=live (right); was previously inverted
- **HITL approval 75s delay in demo** - stopped demo mode from calling the real `/resume` endpoint

## [0.3.2] - 2026-07-01

### Changed
- Bumped UI font sizes for better readability

### Fixed
- Demo simulation now populates confidence and artifact counts at completion

## [0.3.1] - 2026-07-01

### Fixed
- Corrected `astream` tuple unpacking for the specific LangGraph version deployed on Vercel
- Fixed LangSmith trace link

## [0.3.0] - 2026-07-01

### Added
- **Real graph streaming** - `/stream` endpoint now connects to the live LangGraph supervisor via `astream(stream_mode="updates")`
- **HITL resume endpoint** - `POST /threads/{id}/resume` for continuing after `interrupt()` gates
- **Run info panel** - step counter, confidence display, and artifact counter in the UI
- **SSE streaming** - all inference flows use `text/event-stream` for real-time output

### Changed
- UI output area upgraded from static text to streaming pre-formatted block

## [0.2.0] - 2026-06-30

### Added
- **LangGraph Supervisor GA** - supervisor + 6 specialist subgraphs (SRE Analyst, Knowledge, Researcher, Coder, Communicator, Evaluator)
- **14 production tools** - Tavily, Code Executor, Postgres, GitHub, Slack, Browser, Prometheus, Runbook, Arxiv, Wikipedia, Email, Calendar, FS, Memory
- **Hybrid RAG** - MultiQuery → Cohere Rerank → LLM Grader → HyDE, PGVector + BM25
- **7 agentic loops** - Perception-Plan-Act-Reflect, Supervisor-Worker, RAG Self-Correction, ReAct, HITL, Eval-Driven, Memory Consolidation
- **LangGraph Studio** support via `langgraph dev`
- **Docker Compose** infrastructure (Postgres, PGVector, Redis)
- **CI** with eval gating (faithfulness > 0.82)
- **LangServe** `/invoke` and `/docs` endpoints
- **MIT License**