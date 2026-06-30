# packages/rag/vectorstore.py
import os
def get_embeddings():
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import OpenAIEmbeddings
            # CacheBackedEmbeddings moved around in 0.3 – try both paths
            try:
                from langchain.embeddings import CacheBackedEmbeddings
                from langchain.storage import LocalFileStore
            except ImportError:
                from langchain_community.embeddings import CacheBackedEmbeddings
                from langchain_community.storage import LocalFileStore
            underlying = OpenAIEmbeddings(model="text-embedding-3-small")
            store = LocalFileStore("./.cache/embeddings")
            return CacheBackedEmbeddings.from_bytes_store(underlying, store, namespace="openai")
        except Exception:
            try:
                from langchain_openai import OpenAIEmbeddings
                return OpenAIEmbeddings()
            except Exception:
                pass
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
    # Fallback FAISS in-memory – may not be installed on Vercel
    try:
        from langchain_community.vectorstores import FAISS
        return FAISS.from_texts(["AEGIS seed doc: checkout latency runbook v2.4", "Slack incident #342 checkout spike us-east"], embeddings)
    except Exception:
        return None
