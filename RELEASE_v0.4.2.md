AEGIS v0.4.2 — Clean Streaming Output & Smart Post-HITL Resume

## What's New

This release fixes three issues that made live inference output hard to follow: duplicate content, leaked routing metadata, and the full graph re-running after HITL approval on Vercel serverless.

## Fixes

### Duplicate content eliminated
Added content-hash deduplication to the streaming generator. When the LangGraph supervisor revisits a node (e.g. SRE Analyst called twice), identical output is now emitted only once.

### Routing metadata no longer leaks into sub-agents
The Supervisor's `Route` and `Plan` fields were appearing under every node's output block. These are now restricted to the Supervisor node only, so SRE Analyst, Knowledge, Coder, etc. only show their own findings.

### Post-HITL resume is checkpoint-aware
On Vercel serverless, in-memory LangGraph checkpoints (MemorySaver) are lost between function invocations. The previous `Command(resume=...)` approach would restart the entire graph from scratch, causing all agents to re-run and a second HITL interrupt to fire.

The resume endpoint now:
- Accepts the list of already-completed nodes from the frontend
- Only simulates the evaluator and communicator if they haven't run yet
- If HITL fired on the last node (e.g. communicator/slack_post), it just confirms approval with no duplicate output

## Demo

Visit [aegis-api-two.vercel.app/ui](https://aegis-api-two.vercel.app/ui), switch to **Live inference**, and click Run AEGIS to see the clean streaming flow end-to-end.

## Full Changelog

See [CHANGELOG.md](https://github.com/devtechedge/aegis_vercel/blob/main/CHANGELOG.md)