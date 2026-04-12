"""Experimental stub provider for cordless sessions."""

from __future__ import annotations

from agent_sessions.models import SessionDetail, SessionSummary


def list_cordless_sessions(
    directory: str | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Return no sessions until cordless storage integration is implemented."""
    return []


def get_cordless_session_detail(
    session_id: str,
    limit: int = 100,
) -> SessionDetail | None:
    """Return no detail until cordless storage integration is implemented."""
    return None
