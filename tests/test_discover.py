"""Tests for the top-level discover_sessions API."""

from __future__ import annotations

from unittest.mock import patch

from agent_sessions import discover_sessions, get_session_detail, RunnerType
from agent_sessions.models import SessionSummary, SessionDetail, SessionMessage


def _make_summary(id: str, runner_type: RunnerType, activity: str) -> SessionSummary:
    return SessionSummary(
        id=id,
        runner_type=runner_type,
        directory="/tmp",
        last_activity=activity,
        message_count=1,
        is_running=False,
    )


def test_discover_sessions_combines_providers():
    with (
        patch("agent_sessions.list_claude_sessions", return_value=[
            _make_summary("c1", RunnerType.CLAUDE_CODE, "2026-01-03T00:00:00Z"),
        ]),
        patch("agent_sessions.list_codex_sessions", return_value=[
            _make_summary("x1", RunnerType.CODEX, "2026-01-02T00:00:00Z"),
        ]),
        patch("agent_sessions.list_pi_sessions", return_value=[
            _make_summary("p1", RunnerType.PI, "2026-01-01T00:00:00Z"),
        ]),
    ):
        sessions = discover_sessions()

    assert len(sessions) == 3
    # Sorted by last_activity descending
    assert [s.id for s in sessions] == ["c1", "x1", "p1"]


def test_discover_sessions_filter_by_runner_type():
    with (
        patch("agent_sessions.list_claude_sessions", return_value=[]) as mock_claude,
        patch("agent_sessions.list_codex_sessions", return_value=[
            _make_summary("x1", RunnerType.CODEX, "2026-01-01T00:00:00Z"),
        ]) as mock_codex,
        patch("agent_sessions.list_pi_sessions", return_value=[]) as mock_pi,
    ):
        sessions = discover_sessions(runner_type=RunnerType.CODEX)

    assert len(sessions) == 1
    assert sessions[0].id == "x1"
    mock_claude.assert_not_called()
    mock_pi.assert_not_called()
    mock_codex.assert_called_once()


def test_discover_sessions_respects_limit():
    summaries = [
        _make_summary(f"s{i}", RunnerType.CLAUDE_CODE, f"2026-01-{i+1:02d}T00:00:00Z")
        for i in range(10)
    ]
    with (
        patch("agent_sessions.list_claude_sessions", return_value=summaries),
        patch("agent_sessions.list_codex_sessions", return_value=[]),
        patch("agent_sessions.list_pi_sessions", return_value=[]),
    ):
        sessions = discover_sessions(limit=3)

    assert len(sessions) == 3


def test_get_session_detail_routes_to_provider():
    detail = SessionDetail(
        id="c1",
        runner_type=RunnerType.CLAUDE_CODE,
        directory="/tmp",
        last_activity="2026-01-01T00:00:00Z",
        message_count=1,
        is_running=False,
        messages=[SessionMessage(role="user", content="hi")],
    )
    with patch("agent_sessions.get_claude_session_detail", return_value=detail) as mock:
        result = get_session_detail("c1", RunnerType.CLAUDE_CODE)

    assert result is detail
    mock.assert_called_once_with("c1", limit=100)


def test_get_session_detail_returns_none_for_not_found():
    with patch("agent_sessions.get_claude_session_detail", return_value=None):
        result = get_session_detail("nonexistent", RunnerType.CLAUDE_CODE)
    assert result is None
