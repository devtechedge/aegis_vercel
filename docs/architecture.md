# AEGIS Architecture ADRs

## ADR-001: LangGraph over CrewAI
LangGraph provides durable checkpointing (PostgresSaver), native HITL `interrupt()`, and LangSmith first-class tracing. Required for enterprise auditability.

## ADR-002: PGVector over Qdrant
PGVector keeps vector + transactional data co-located in Postgres, simplifying ops. Qdrant adapter interface is retained for swappability.

## ADR-003: Supervisor-Worker vs Swarm
Supervisor gives deterministic routing + critic feedback loop, essential for incident triage compliance.

## Agentic Loops
All 7 loops implemented and visible in LangSmith traces with `metadata.loop_iteration`.

## Security
- Pydantic validation everywhere
- SQL read-only unless HITL approved
- Sandboxed code_executor
- Secret scanning via .env
