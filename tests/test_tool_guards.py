"""Allow-list guards on the mock tool registry.

These are the Phase B unit tests for the threat-model controls in SECURITY.md.
"""
from packages.tools.registry import (
    ALL_TOOLS,
    code_executor,
    file_system_tool,
    github_toolkit,
    postgres_sql_toolkit,
    send_email_tool,
    slack_toolkit,
)


def test_sql_writes_blocked():
    for query in (
        "DELETE FROM users",
        "UPDATE checkout SET latency = 0",
        "INSERT INTO incidents VALUES (1)",
        "DROP TABLE metrics",
        "ALTER TABLE checkout ADD COLUMN x int",
    ):
        result = postgres_sql_toolkit.invoke({"query": query})
        assert "WRITE_BLOCKED" in result, query


def test_sql_reads_not_blocked():
    result = postgres_sql_toolkit.invoke({"query": "SELECT p95 FROM checkout_latency"})
    assert "WRITE_BLOCKED" not in result


def test_filesystem_path_traversal_blocked():
    for path in ("../secrets.env", "/etc/passwd", "foo/../../etc/shadow"):
        result = file_system_tool.invoke({"path": path, "action": "read"})
        assert result == "SECURITY_BLOCKED", path


def test_filesystem_normal_path_allowed():
    result = file_system_tool.invoke({"path": "runbooks/checkout.md", "action": "read"})
    assert result != "SECURITY_BLOCKED"


def test_code_executor_rejects_non_python():
    result = code_executor.invoke({"code": "puts 1", "language": "ruby"})
    assert "Only python" in result


def test_code_executor_restricted_builtins():
    result = code_executor.invoke({"code": "print(sum(range(5)))", "language": "python"})
    assert "10" in result
    blocked = code_executor.invoke({"code": "open('/etc/passwd')", "language": "python"})
    assert "SECURITY_BLOCKED" in blocked
    banned_import = code_executor.invoke({"code": "import os", "language": "python"})
    assert "SECURITY_BLOCKED" in banned_import


def test_github_pr_is_hitl_gated():
    result = github_toolkit.invoke({"action": "create_pr", "repo": "devtechedge/aegis_vercel"})
    assert "HITL_REQUIRED" in result


def test_slack_post_is_hitl_gated():
    result = slack_toolkit.invoke({"action": "post_message", "channel": "#incidents", "message": "hi"})
    assert "HITL_REQUIRED" in result


def test_email_always_hitl_gated():
    result = send_email_tool.invoke({"to": "sre@example.com", "subject": "x", "body": "y"})
    assert "HITL_REQUIRED" in result


def test_registry_still_has_hitl_tools():
    names = {t.name for t in ALL_TOOLS}
    assert {"code_executor", "postgres_sql_toolkit", "file_system_tool", "send_email_tool"} <= names
