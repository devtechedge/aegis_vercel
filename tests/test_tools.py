def test_all_tools_load():
    from packages.tools.registry import ALL_TOOLS
    assert len(ALL_TOOLS) >= 14
    names = [t.name for t in ALL_TOOLS]
    assert "tavily_search" in names
    assert "prometheus_metrics_tool" in names
