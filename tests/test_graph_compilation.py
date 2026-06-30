def test_graph_compiles():
    from packages.aegis_graph.supervisor import graph
    assert graph is not None

def test_subgraphs():
    from packages.aegis_graph.subgraphs.knowledge_agent import knowledge_agent
    from packages.aegis_graph.subgraphs.sre_analyst import sre_agent
    from packages.aegis_graph.subgraphs.coder import coder_agent
    assert knowledge_agent and sre_agent and coder_agent
