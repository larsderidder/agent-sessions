"""Tests for running session detection."""

from __future__ import annotations

from unittest.mock import patch
import subprocess

from agent_sessions.running import (
    find_running_claude_sessions,
    find_running_codex_sessions,
    find_running_pi_sessions,
    is_claude_session_running,
    is_codex_session_running,
    is_pi_session_running,
)


def _mock_ps(stdout: str):
    """Return a mock for subprocess.run that returns the given ps output."""
    result = subprocess.CompletedProcess(["ps", "aux"], 0, stdout=stdout, stderr="")
    return patch("agent_sessions.running.subprocess.run", return_value=result)


def test_find_running_claude_sessions():
    ps_output = (
        "lars  12345  0.5  1.0  100000  50000  ?  S  10:00  0:05 claude --resume a1b2c3d4-e5f6-7890-abcd-ef1234567890\n"
        "lars  12346  0.1  0.5  50000  25000  ?  S  10:01  0:01 vim test.py\n"
    )
    with _mock_ps(ps_output):
        result = find_running_claude_sessions()
    assert result == {"a1b2c3d4-e5f6-7890-abcd-ef1234567890"}


def test_find_running_claude_sessions_empty():
    with _mock_ps("lars  12345  0.1  0.5  50000  25000  ?  S  10:01  0:01 vim test.py\n"):
        result = find_running_claude_sessions()
    assert result == set()


def test_find_running_codex_sessions():
    ps_output = "lars  12345  0.5  1.0  100000  50000  ?  S  10:00  0:05 codex resume a1b2c3d4-e5f6-7890-abcd-ef1234567890\n"
    with _mock_ps(ps_output):
        result = find_running_codex_sessions()
    assert result == {"a1b2c3d4-e5f6-7890-abcd-ef1234567890"}


def test_find_running_pi_sessions():
    ps_output = (
        "lars  12345  0.5  1.0  100000  50000  ?  S  10:00  0:05 "
        "/home/lars/.nvm/versions/node/v22/bin/pi-coding-agent "
        "d6660987-06ac-427d-b751-1232e8b88ca2\n"
    )
    with _mock_ps(ps_output):
        result = find_running_pi_sessions()
    assert result == {"d6660987-06ac-427d-b751-1232e8b88ca2"}


def test_is_claude_session_running():
    ps_output = "lars  12345  0.5  1.0  100000  50000  ?  S  10:00  0:05 claude --resume abc-def-ghi-jkl-mnopqrstuvwxyz1234\n"
    with _mock_ps(ps_output):
        assert is_claude_session_running("abc-def-ghi-jkl-mnopqrstuvwxyz1234") is True
        # Not called again; find_running_claude_sessions caches nothing
    with _mock_ps(ps_output):
        assert is_claude_session_running("other-id") is False


def test_subprocess_timeout_returns_empty():
    with patch(
        "agent_sessions.running.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ps", timeout=5),
    ):
        assert find_running_claude_sessions() == set()
        assert find_running_codex_sessions() == set()
        assert find_running_pi_sessions() == set()
