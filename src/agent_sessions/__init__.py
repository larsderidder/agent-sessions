"""agent-sessions: Discover and inspect local AI coding agent sessions."""

from agent_sessions.models import (
    RunnerType,
    SessionDetail,
    SessionMessage,
    SessionSummary,
)
from agent_sessions.providers.claude_code import (
    list_claude_sessions,
    get_claude_session_detail,
)
from agent_sessions.providers.codex import (
    list_codex_sessions,
    get_codex_session_detail,
)
from agent_sessions.providers.opencode import (
    list_opencode_sessions,
    get_opencode_session_detail,
)
from agent_sessions.providers.discordo import (
    list_discordo_sessions,
    get_discordo_session_detail,
)
from agent_sessions.providers.endcord import (
    list_endcord_sessions,
    get_endcord_session_detail,
)
from agent_sessions.providers.cordless import (
    list_cordless_sessions,
    get_cordless_session_detail,
)
from agent_sessions.providers.pi import (
    list_pi_sessions,
    get_pi_session_detail,
)
from agent_sessions.running import (
    is_claude_session_running,
    is_codex_session_running,
    is_cordless_session_running,
    is_discordo_session_running,
    is_endcord_session_running,
    is_opencode_session_running,
    is_pi_session_running,
)


def discover_sessions(
    directory: str | None = None,
    runner_type: RunnerType | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Discover agent sessions from all supported providers.

    Scans the local machine for recent and running agent sessions.

    Args:
        directory: Filter to sessions for this project directory.
        runner_type: Filter to a specific agent type.
        limit: Maximum sessions to return.

    Returns:
        List of session summaries, sorted by last_activity descending.
    """
    sessions: list[SessionSummary] = []

    if runner_type is None or runner_type == RunnerType.CLAUDE_CODE:
        sessions.extend(list_claude_sessions(directory=directory, limit=limit))
    if runner_type is None or runner_type == RunnerType.CODEX:
        sessions.extend(list_codex_sessions(directory=directory, limit=limit))
    if runner_type is None or runner_type == RunnerType.OPENCODE:
        sessions.extend(list_opencode_sessions(directory=directory, limit=limit))
    if runner_type is None or runner_type == RunnerType.DISCORDO:
        sessions.extend(list_discordo_sessions(directory=directory, limit=limit))
    if runner_type is None or runner_type == RunnerType.ENDCORD:
        sessions.extend(list_endcord_sessions(directory=directory, limit=limit))
    if runner_type is None or runner_type == RunnerType.CORDLESS:
        sessions.extend(list_cordless_sessions(directory=directory, limit=limit))
    if runner_type is None or runner_type == RunnerType.PI:
        sessions.extend(list_pi_sessions(directory=directory, limit=limit))

    sessions.sort(key=lambda s: s.last_activity, reverse=True)
    return sessions[:limit]


def get_session_detail(
    session_id: str,
    runner_type: RunnerType,
    limit: int = 100,
) -> SessionDetail | None:
    """Load full session detail with message history.

    Args:
        session_id: The session UUID.
        runner_type: Which agent created the session.
        limit: Maximum messages to return.

    Returns:
        Session detail with messages, or None if not found.
    """
    if runner_type == RunnerType.CLAUDE_CODE:
        return get_claude_session_detail(session_id, limit=limit)
    if runner_type == RunnerType.CODEX:
        return get_codex_session_detail(session_id, limit=limit)
    if runner_type == RunnerType.OPENCODE:
        return get_opencode_session_detail(session_id, limit=limit)
    if runner_type == RunnerType.DISCORDO:
        return get_discordo_session_detail(session_id, limit=limit)
    if runner_type == RunnerType.ENDCORD:
        return get_endcord_session_detail(session_id, limit=limit)
    if runner_type == RunnerType.CORDLESS:
        return get_cordless_session_detail(session_id, limit=limit)
    if runner_type == RunnerType.PI:
        return get_pi_session_detail(session_id, limit=limit)
    return None


__all__ = [
    # Main API
    "discover_sessions",
    "get_session_detail",
    # Models
    "RunnerType",
    "SessionDetail",
    "SessionMessage",
    "SessionSummary",
    # Per-provider
    "list_claude_sessions",
    "get_claude_session_detail",
    "list_codex_sessions",
    "get_codex_session_detail",
    "list_opencode_sessions",
    "get_opencode_session_detail",
    "list_discordo_sessions",
    "get_discordo_session_detail",
    "list_endcord_sessions",
    "get_endcord_session_detail",
    "list_cordless_sessions",
    "get_cordless_session_detail",
    "list_pi_sessions",
    "get_pi_session_detail",
    # Process detection
    "is_claude_session_running",
    "is_codex_session_running",
    "is_discordo_session_running",
    "is_endcord_session_running",
    "is_cordless_session_running",
    "is_opencode_session_running",
    "is_pi_session_running",
]
