"""Experimental stub provider for endcord sessions."""

from __future__ import annotations

from agent_sessions.models import SessionDetail, SessionSummary


def list_endcord_sessions(
    directory: str | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Return no sessions until endcord storage integration is implemented."""
    return []


def get_endcord_session_detail(
    session_id: str,
    limit: int = 100,
) -> SessionDetail | None:
    """Return no detail until endcord storage integration is implemented."""
    return None
