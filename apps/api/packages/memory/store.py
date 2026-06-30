# packages/memory/store.py
import os
def get_short_term_memory(session_id: str = "default"):
    """ConversationSummaryBufferMemory via Redis, fallback in-memory"""
    try:
        import redis
        from langchain.memory import ConversationSummaryBufferMemory
        from langchain_openai import ChatOpenAI
        if os.getenv("REDIS_URL") and os.getenv("OPENAI_API_KEY"):
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            return ConversationSummaryBufferMemory(llm=llm, max_token_limit=1000, return_messages=True)
    except Exception:
        pass
    from langchain.memory import ConversationBufferMemory
    return ConversationBufferMemory(return_messages=True)

def get_long_term_retriever():
    from packages.rag.vectorstore import get_vectorstore
    vs = get_vectorstore()
    if vs:
        return vs.as_retriever()
    return None

def distill_memory(task: str, artifacts: dict) -> dict:
    """Memory Consolidation Loop - extract facts/entities"""
    facts = [f"Task completed: {task[:120]}", f"Confidence: {artifacts.get('confidence', 0)}"]
    # In production, upsert to PGVector
    return {"facts_stored": len(facts), "facts": facts}
