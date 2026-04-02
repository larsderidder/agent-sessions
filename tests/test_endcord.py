"""Tests for endcord stub provider support."""

from __future__ import annotations

from agent_sessions.providers.endcord import (
    get_endcord_session_detail,
    list_endcord_sessions,
)


def test_list_endcord_sessions_returns_empty_list() -> None:
    assert list_endcord_sessions() == []


def test_get_endcord_session_detail_returns_none() -> None:
    assert get_endcord_session_detail("endcord-session") is None
