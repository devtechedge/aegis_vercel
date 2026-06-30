# AEGIS API

Production-ready FastAPI backend for **AEGIS** — Autonomous Enterprise Graph Intelligence System.

## Live Deployment

- **URL**: [https://aegis-api-two.vercel.app](https://aegis-api-two.vercel.app)
- **API Documentation**: [https://aegis-api-two.vercel.app/docs](https://aegis-api-two.vercel.app/docs)

## Status

- ✅ Successfully deployed on Vercel
- ✅ All core endpoints working
- ✅ Debug logging enabled
- ✅ Root Directory: `apps/api`

## Endpoints

| Method | Endpoint     | Description              |
|--------|--------------|--------------------------|
| GET    | `/`          | API status               |
| GET    | `/health`    | System health check      |
| GET    | `/debug`     | Runtime environment info |
| GET    | `/docs`      | Interactive API docs     |

## Tech Stack

- Python 3.12 + FastAPI
- Deployed on Vercel Serverless Functions
- Framework: FastAPI

## Environment Variables

This project supports the following environment variables for full functionality:

### Required for Basic Use
None (the current deployment works without any keys).

### Recommended for Full Features

| Variable              | Description                          | Example                          | Where to Get |
|-----------------------|--------------------------------------|----------------------------------|--------------|
| `OPENAI_API_KEY`      | OpenAI API key                       | `sk-...`                         | [platform.openai.com](https://platform.openai.com) |
| `LANGCHAIN_API_KEY`   | LangSmith tracing key                | `ls__...`                        | [smith.langchain.com](https://smith.langchain.com) |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing            | `true`                           | — |
| `LANGCHAIN_PROJECT`   | LangSmith project name               | `aegis-production`               | — |
| `COHERE_API_KEY`      | Cohere reranker (optional)           | `...`                            | [cohere.com](https://cohere.com) |

### How to Add Environment Variables

1. Go to your Vercel project dashboard
2. Click **Settings** → **Environment Variables**
3. Add the variables above
4. Select **Production**, **Preview**, and **Development**
5. Click **Save**
6. Redeploy the project (or push a new commit)

> **Tip**: Start with `OPENAI_API_KEY` and `LANGCHAIN_API_KEY` for the most value.

## How to Deploy (for Contributors)

### Prerequisites
- GitHub account
- Vercel account (free tier is sufficient)

### Steps

1. **Fork or Clone this repository**

2. **Create a new Vercel project**
   - Go to [vercel.com/new](https://vercel.com/new)
   - Import this repository (`aegis_vercel`)

3. **Configure the project**
   - **Project Name**: `aegis-api` (or your preferred name)
   - **Root Directory**: `apps/api`
   - **Framework Preset**: `FastAPI`

4. **Deploy**
   - Click **Deploy**

5. **(Optional) Add Environment Variables**
   - See the **Environment Variables** section above

### Local Development

```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload
```

Then visit: http://localhost:8000/docs

## Repository Relationship

This repository (`aegis_vercel`) serves as the **clean Vercel deployment target**.

The main development repository (containing the full LangChain, LangGraph, RAG, and multi-agent implementation) is:

→ [github.com/devtechedge/aegis](https://github.com/devtechedge/aegis)

## Architecture

- Root Directory: `apps/api`
- Routers: `threads`, `fleet`
- Graceful fallbacks for optional dependencies (LangServe, LangGraph, etc.)

## Next Steps / Roadmap

This serves as the stable foundation. Future updates will include:

- LangGraph Supervisor integration
- Full RAG pipeline with self-correction
- LangServe endpoints (`/invoke`, `/stream`)
- Additional specialist agents

---

**Built with ❤️ using the LangChain ecosystem**
