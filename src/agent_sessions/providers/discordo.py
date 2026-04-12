"""Experimental stub provider for discordo sessions."""

from __future__ import annotations

from agent_sessions.models import SessionDetail, SessionSummary


def list_discordo_sessions(
    directory: str | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Return no sessions until discordo storage integration is implemented."""
    return []


def get_discordo_session_detail(
    session_id: str,
    limit: int = 100,
) -> SessionDetail | None:
    """Return no detail until discordo storage integration is implemented."""
    return None
