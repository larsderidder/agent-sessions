"""Tests for session models."""

from agent_sessions.models import RunnerType, SessionSummary, SessionDetail, SessionMessage


def test_runner_type_values():
    assert RunnerType.CLAUDE_CODE.value == "claude_code"
    assert RunnerType.CODEX.value == "codex"
    assert RunnerType.PI.value == "pi"


def test_session_summary():
    s = SessionSummary(
        id="abc-123",
        runner_type=RunnerType.CLAUDE_CODE,
        directory="/home/user/project",
        last_activity="2026-01-01T00:00:00Z",
        message_count=5,
        is_running=True,
    )
    assert s.id == "abc-123"
    assert s.first_prompt is None
    assert s.is_running is True


def test_session_detail_inherits_summary():
    d = SessionDetail(
        id="abc-123",
        runner_type=RunnerType.PI,
        directory="/tmp",
        last_activity="2026-01-01T00:00:00Z",
        message_count=1,
        is_running=False,
        messages=[SessionMessage(role="user", content="hello")],
    )
    assert isinstance(d, SessionSummary)
    assert len(d.messages) == 1
    assert d.messages[0].thinking is None


def test_session_message_with_thinking():
    m = SessionMessage(
        role="assistant",
        content="Hi there",
        thinking="User greeted me",
        timestamp="2026-01-01T00:00:00Z",
    )
    assert m.thinking == "User greeted me"
