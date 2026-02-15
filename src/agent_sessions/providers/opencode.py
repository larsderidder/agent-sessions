"""OpenCode session discovery and parsing.

OpenCode stores sessions in a per-project SQLite database at
``<project>/.opencode/opencode.db``.  Unlike Claude Code, Codex, and Pi,
there is no central session directory.  Discovery works by scanning a
configurable set of directories for ``.opencode/opencode.db`` files.

The database schema has two relevant tables:

- ``sessions``: id, title, message_count, cost, created_at, updated_at
- ``messages``: id, session_id, role, parts (JSON), model, created_at,
  updated_at, finished_at

The ``parts`` column stores a JSON array of typed content parts::

    [
      {"type": "text", "data": {"text": "Hello"}},
      {"type": "reasoning", "data": {"thinking": "..."}},
      {"type": "tool_call", "data": {"id": "...", "name": "...", ...}},
      {"type": "tool_result", "data": {"content": "...", ...}},
      {"type": "finish", "data": {"reason": "end_turn", "time": 1234567890}},
    ]

Timestamps in the database are Unix epoch seconds.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from agent_sessions.models import (
    RunnerType,
    SessionDetail,
    SessionMessage,
    SessionSummary,
)
from agent_sessions.running import find_running_opencode_sessions

logger = logging.getLogger(__name__)

DB_FILENAME = "opencode.db"
OPENCODE_DIR = ".opencode"


def _search_dirs() -> list[Path]:
    """Return the directories to scan for OpenCode project databases.

    Uses the ``OPENCODE_SEARCH_DIRS`` environment variable (colon-separated
    list of paths) if set.  Otherwise defaults to the user's home directory.
    """
    value = os.environ.get("OPENCODE_SEARCH_DIRS")
    if value:
        return [Path(p).expanduser() for p in value.split(":") if p.strip()]
    return [Path.home()]


def _find_databases(roots: list[Path], max_depth: int = 4) -> list[Path]:
    """Recursively find ``opencode.db`` files under the given roots.

    Only looks inside ``.opencode/`` directories up to *max_depth* levels
    below each root.  Skips hidden directories other than ``.opencode``
    and common noise directories (node_modules, .git, __pycache__, etc.).
    """
    skip_dirs = {
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
    }
    results: list[Path] = []

    for root in roots:
        if not root.is_dir():
            continue
        _walk(root, results, skip_dirs, max_depth, 0)

    return results


def _walk(
    directory: Path,
    results: list[Path],
    skip_dirs: set[str],
    max_depth: int,
    depth: int,
) -> None:
    """Depth-limited walk looking for .opencode/opencode.db."""
    if depth > max_depth:
        return

    # Check if this directory itself has .opencode/opencode.db
    candidate = directory / OPENCODE_DIR / DB_FILENAME
    try:
        if candidate.is_file():
            results.append(candidate)
    except (PermissionError, OSError):
        pass

    if depth == max_depth:
        return

    try:
        entries = sorted(directory.iterdir())
    except PermissionError:
        return

    for entry in entries:
        if not entry.is_dir():
            continue
        name = entry.name
        # Skip .opencode itself (already checked), other hidden dirs, and noise
        if name == OPENCODE_DIR:
            continue
        if name.startswith("."):
            continue
        if name in skip_dirs:
            continue
        _walk(entry, results, skip_dirs, max_depth, depth + 1)


def _directory_from_db_path(db_path: Path) -> str:
    """Infer the project directory from a database path.

    The DB lives at ``<project>/.opencode/opencode.db``, so the project
    directory is two levels up.
    """
    return str(db_path.parent.parent)


def _unix_to_iso(ts: int | float | None) -> str | None:
    """Convert a Unix timestamp (seconds) to an ISO 8601 string."""
    if ts is None or ts == 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _extract_text_parts(parts_json: str) -> tuple[str, str | None]:
    """Extract text content and thinking from a parts JSON string.

    Returns:
        (text_content, thinking_content)
    """
    try:
        parts = json.loads(parts_json)
    except (json.JSONDecodeError, TypeError):
        return "", None

    if not isinstance(parts, list):
        return "", None

    texts: list[str] = []
    thinking_parts: list[str] = []

    for part in parts:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type", "")
        data = part.get("data", {})
        if not isinstance(data, dict):
            continue

        if part_type == "text":
            text = data.get("text", "")
            if text:
                texts.append(text)
        elif part_type == "reasoning":
            thinking = data.get("thinking", "")
            if thinking:
                thinking_parts.append(thinking)

    text_content = "\n".join(texts)
    thinking_content = "\n\n".join(thinking_parts) if thinking_parts else None
    return text_content, thinking_content


def _extract_user_prompt(parts_json: str) -> str | None:
    """Extract the user's prompt text from a parts JSON string.

    Skips tool results and system-generated content.
    """
    try:
        parts = json.loads(parts_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(parts, list):
        return None

    for part in parts:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type", "")
        data = part.get("data", {})
        if not isinstance(data, dict):
            continue

        if part_type == "tool_result":
            return None  # This is a tool result message, not a user prompt
        if part_type == "text":
            text = data.get("text", "")
            if text:
                return text.strip()[:200]

    return None


def _query_sessions(db_path: Path) -> list[dict]:
    """Query the sessions table from an OpenCode database."""
    results = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT id, title, message_count, cost, created_at, updated_at "
                "FROM sessions WHERE parent_session_id IS NULL "
                "ORDER BY updated_at DESC"
            )
            results = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "Failed to query OpenCode sessions",
            extra={"db_path": str(db_path), "error": str(exc)},
        )
    return results


def _query_first_last_prompts(
    conn: sqlite3.Connection, session_id: str
) -> tuple[str | None, str | None]:
    """Get the first and last user prompts for a session."""
    first_prompt: str | None = None
    last_prompt: str | None = None

    try:
        cursor = conn.execute(
            "SELECT parts FROM messages "
            "WHERE session_id = ? AND role = 'user' "
            "ORDER BY created_at ASC",
            (session_id,),
        )
        for row in cursor:
            prompt = _extract_user_prompt(row[0])
            if prompt:
                if first_prompt is None:
                    first_prompt = prompt
                last_prompt = prompt
    except Exception:
        pass

    return first_prompt, last_prompt


def _query_messages(
    conn: sqlite3.Connection, session_id: str, limit: int = 100
) -> list[SessionMessage]:
    """Query messages for a session, applying the limit to the most recent."""
    messages: list[SessionMessage] = []

    try:
        cursor = conn.execute(
            "SELECT role, parts, created_at FROM messages "
            "WHERE session_id = ? AND role IN ('user', 'assistant') "
            "ORDER BY created_at ASC",
            (session_id,),
        )
        all_rows = cursor.fetchall()
        # Apply limit to most recent
        if len(all_rows) > limit:
            all_rows = all_rows[-limit:]

        for row in all_rows:
            role, parts_json, created_at = row
            timestamp = _unix_to_iso(created_at)

            if role == "user":
                text, _ = _extract_text_parts(parts_json)
                if text:
                    messages.append(
                        SessionMessage(
                            role="user",
                            content=text,
                            timestamp=timestamp,
                        )
                    )
            elif role == "assistant":
                text, thinking = _extract_text_parts(parts_json)
                if text or thinking:
                    messages.append(
                        SessionMessage(
                            role="assistant",
                            content=text,
                            thinking=thinking,
                            timestamp=timestamp,
                        )
                    )
    except Exception as exc:
        logger.warning(
            "Failed to query OpenCode messages",
            extra={"session_id": session_id, "error": str(exc)},
        )

    return messages


def list_opencode_sessions(
    directory: str | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Discover OpenCode sessions.

    Scans for ``.opencode/opencode.db`` files under the configured search
    directories and reads session metadata from each database.

    Args:
        directory: Filter to sessions for this specific project directory.
            When provided, only the ``.opencode/opencode.db`` in that
            directory is checked.
        limit: Maximum sessions to return.

    Returns:
        List of session summaries sorted by last_activity descending.
    """
    running_sessions = find_running_opencode_sessions()

    if directory:
        # Only check the specific directory
        db_path = Path(directory) / OPENCODE_DIR / DB_FILENAME
        db_paths = [db_path] if db_path.is_file() else []
    else:
        db_paths = _find_databases(_search_dirs())

    sessions: list[SessionSummary] = []

    for db_path in db_paths:
        project_dir = _directory_from_db_path(db_path)

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(
                    "SELECT id, title, message_count, cost, created_at, updated_at "
                    "FROM sessions WHERE parent_session_id IS NULL "
                    "ORDER BY updated_at DESC"
                )
                for row in cursor:
                    session_id = row["id"]
                    updated_at = row["updated_at"]
                    last_activity = _unix_to_iso(updated_at) or ""

                    first_prompt, last_prompt = _query_first_last_prompts(conn, session_id)
                    # Use title as fallback for first_prompt
                    title = row["title"]
                    if not first_prompt and title:
                        first_prompt = title[:200]

                    sessions.append(
                        SessionSummary(
                            id=session_id,
                            runner_type=RunnerType.OPENCODE,
                            directory=project_dir,
                            first_prompt=first_prompt,
                            last_prompt=last_prompt,
                            last_activity=last_activity,
                            message_count=row["message_count"],
                            is_running=session_id in running_sessions,
                        )
                    )
            finally:
                conn.close()
        except Exception as exc:
            logger.warning(
                "Failed to read OpenCode database",
                extra={"db_path": str(db_path), "error": str(exc)},
            )

    sessions.sort(key=lambda s: s.last_activity, reverse=True)
    return sessions[:limit]


def _find_database_for_session(session_id: str) -> Path | None:
    """Find which database contains a given session ID."""
    db_paths = _find_databases(_search_dirs())

    for db_path in db_paths:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                cursor = conn.execute(
                    "SELECT 1 FROM sessions WHERE id = ? LIMIT 1",
                    (session_id,),
                )
                if cursor.fetchone():
                    return db_path
            finally:
                conn.close()
        except Exception:
            continue

    return None


def get_opencode_session_detail(
    session_id: str,
    limit: int = 100,
) -> SessionDetail | None:
    """Load full message history for an OpenCode session.

    Args:
        session_id: The session UUID.
        limit: Maximum messages to return.

    Returns:
        Session detail with messages, or None if not found.
    """
    db_path = _find_database_for_session(session_id)
    if not db_path:
        return None

    project_dir = _directory_from_db_path(db_path)
    running_sessions = find_running_opencode_sessions()

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT id, title, message_count, cost, created_at, updated_at "
                "FROM sessions WHERE id = ? LIMIT 1",
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            updated_at = row["updated_at"]
            last_activity = _unix_to_iso(updated_at) or ""

            first_prompt, last_prompt = _query_first_last_prompts(conn, session_id)
            title = row["title"]
            if not first_prompt and title:
                first_prompt = title[:200]

            messages = _query_messages(conn, session_id, limit=limit)

            return SessionDetail(
                id=session_id,
                runner_type=RunnerType.OPENCODE,
                directory=project_dir,
                first_prompt=first_prompt,
                last_prompt=last_prompt,
                last_activity=last_activity,
                message_count=row["message_count"],
                is_running=session_id in running_sessions,
                messages=messages,
            )
        finally:
            conn.close()
    except Exception as exc:
        logger.warning(
            "Failed to read OpenCode session detail",
            extra={"session_id": session_id, "error": str(exc)},
        )
        return None
