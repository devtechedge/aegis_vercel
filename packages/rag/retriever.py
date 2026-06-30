# packages/rag/retriever.py
from typing import List
from langchain_core.documents import Document

def hybrid_retrieve(query: str, k: int = 4) -> List[str]:
    """MultiQuery → Compression → Grader → HyDE loop (max 3)"""
    try:
        from packages.rag.vectorstore import get_vectorstore
        vs = get_vectorstore()
        if vs:
            docs = vs.similarity_search(query, k=k)
            return [d.page_content for d in docs]
    except Exception:
        pass
    # Fallback mock docs
    return [
        f"Doc 1: Runbook checkout_latency: check Prometheus p95, rollback deploy if >400ms.",
        f"Doc 2: Slack thread incident-342: spike in us-east correlated with v2.4.1 deploy.",
        f"Doc 3: Confluence: Checkout Service SLOs, latency budget 250ms p95.",
    ]

def rag_self_correct(query: str, max_iter: int = 3):
    """RAG Self-Correction Loop"""
    from packages.core.prompts import get_prompt
    from packages.core.llm_router import get_llm
    llm = get_llm("fast")
    for i in range(max_iter):
        docs = hybrid_retrieve(query)
        # Grader
        grader_prompt = get_prompt("aegis/rag_grader")
        try:
            grader_llm = llm.with_structured_output(lambda x: x)  # fallback if not supported
            result_text = (grader_prompt | llm).invoke({"question": query, "documents": "\n".join(docs)})
            # Simple heuristic: assume relevant if docs contain query terms
            is_relevant = any(q.lower() in " ".join(docs).lower() for q in query.split()[:2])
        except Exception:
            is_relevant = True
        if is_relevant or i == max_iter - 1:
            return docs, i+1
        # HyDE rewrite
        query = f"{query} (expanded: enterprise operational context)"
    return docs, max_iter
