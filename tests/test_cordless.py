"""Tests for cordless stub provider support."""

from __future__ import annotations

from agent_sessions.providers.cordless import (
    get_cordless_session_detail,
    list_cordless_sessions,
)


def test_list_cordless_sessions_returns_empty_list() -> None:
    assert list_cordless_sessions() == []


def test_get_cordless_session_detail_returns_none() -> None:
    assert get_cordless_session_detail("cordless-session") is None
