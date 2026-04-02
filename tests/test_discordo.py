"""Tests for discordo stub provider support."""

from __future__ import annotations

from agent_sessions.providers.discordo import (
    get_discordo_session_detail,
    list_discordo_sessions,
)


def test_list_discordo_sessions_returns_empty_list() -> None:
    assert list_discordo_sessions() == []


def test_get_discordo_session_detail_returns_none() -> None:
    assert get_discordo_session_detail("discordo-session") is None
