def test_rag_self_correct():
    from packages.rag.retriever import rag_self_correct
    docs, iters = rag_self_correct("checkout latency spike us-east")
    assert len(docs) >= 1
    assert iters >= 1
