# packages/rag/vectorstore.py
import os
def get_embeddings():
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings
        from langchain.embeddings import CacheBackedEmbeddings
        from langchain.storage import LocalFileStore
        import redis
        try:
            # Redis cache if available
            underlying = OpenAIEmbeddings(model="text-embedding-3-small")
            store = LocalFileStore("./.cache/embeddings")
            return CacheBackedEmbeddings.from_bytes_store(underlying, store, namespace="openai")
        except Exception:
            return OpenAIEmbeddings()
    # Fake for Vercel / offline
    from langchain_core.embeddings import FakeEmbeddings
    return FakeEmbeddings(size=1536)

def get_vectorstore():
    embeddings = get_embeddings()
    # Try PGVector
    pg_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if pg_url and "postgres" in pg_url:
        try:
            from langchain_postgres import PGVector
            return PGVector(embeddings=embeddings, collection_name="aegis_docs", connection=pg_url, use_jsonb=True)
        except Exception:
            pass
    # Fallback FAISS in-memory
    try:
        from langchain_community.vectorstores import FAISS
        return FAISS.from_texts(["AEGIS seed doc: checkout latency runbook v2.4", "Slack incident #342 checkout spike us-east"], embeddings)
    except Exception:
        return None
