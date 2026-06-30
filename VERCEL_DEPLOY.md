# Vercel Deploy Notes – AEGIS v0.2.1

Live: https://aegis-api-two.vercel.app

**Vercel Project Settings**
- Framework Preset: FastAPI
- Root Directory: `apps/api`
- Build Command: (leave empty)
- Install Command: `pip install -r requirements-vercel.txt`
  - Use `requirements.txt` for full local Docker stack (PGVector, FAISS, redis)
  - `requirements-vercel.txt` is slimmed to stay < 150MB / under Vercel 250MB serverless limit
  - Missing deps gracefully fallback to mock tools / FakeListChatModel – API stays green, `graph_loaded: false` until you add LLM keys

**Environment Variables (Vercel → Settings → Environment Variables)**
```
OPENAI_API_KEY=sk-...
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=aegis-production
TAVILY_API_KEY=...
# Optional:
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
DATABASE_URL=postgresql://...  # Neon / Supabase PGVector
REDIS_URL=redis://...
```

Without keys: API boots, `/health` = ok, `/invoke` returns mock output, `graph_loaded: false`.
With `OPENAI_API_KEY + LANGCHAIN_API_KEY`: full Supervisor + 6 agents, LangSmith tracing, RAG loop.

**Endpoints**
- `/` – status
- `/health` – health
- `/docs` – Swagger
- `/invoke` – POST {"input":"...","thread_id":"..."}
- `/stream` – SSE streaming
- `/threads/{id}/resume` – HITL approve
- `/aegis/playground` – LangServe

**Why packages live in `apps/api/packages/`**
Vercel only bundles Root Directory. Canonical code is `apps/api/packages/`, repo-root `packages -> apps/api/packages` symlink keeps local/docker imports working.

To run full stack locally:
```
cp .env.example .env
docker-compose -f infra/docker-compose.yml up
```

That's it – the same code runs serverless on Vercel and full Docker locally.
