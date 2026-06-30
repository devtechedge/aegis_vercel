def test_all_tools_load():
    """Robust test for tool registry loading.
    
    Uses get_tool() helper and checks for core expected tools instead of
    hardcoding exact count (which can fluctuate with mocks/fallbacks).
    """
    from packages.tools.registry import ALL_TOOLS, get_tool

    # Basic sanity: at least the main production tools exist
    assert len(ALL_TOOLS) >= 12, f"Expected >=12 tools, got {len(ALL_TOOLS)}"

    # Core tools that must always be present
    core_tools = [
        "tavily_search",
        "prometheus_metrics_tool",
        "github_toolkit",
        "slack_toolkit",
        "code_executor",
    ]

    tool_names = [t.name for t in ALL_TOOLS]

    for name in core_tools:
        assert name in tool_names, f"Missing expected core tool: {name}"

    # Verify the helper works
    assert get_tool("tavily_search") is not None
    assert get_tool("nonexistent_tool") is None

    # Optional: check that we have at least one HITL-gated tool
    hitl_keywords = ["HITL", "approval", "HITL_REQUIRED"]
    has_hitl = any(
        any(kw in (getattr(t, 'description', '') or '') for kw in hitl_keywords)
        for t in ALL_TOOLS
    )
    assert has_hitl, "Expected at least one HITL-gated tool"