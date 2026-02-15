"""OpenCode session discovery and parsing.

OpenCode stores sessions in a centralized SQLite database at
``~/.local/share/opencode/opencode.db`` (XDG data directory).

The database schema has three relevant tables:

- ``session``: id, project_id, directory, title, time_created, time_updated
- ``message``: id, session_id, data (JSON metadata)
- ``part``: id, message_id, session_id, data (JSON content blocks)

Messages are split into parts, where each part has a type (text, step-start,
step-finish, etc.). User prompts and assistant responses are extracted from
parts with ``type: "text"``.

Timestamps in the database are Unix epoch milliseconds.
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


def _opencode_db_path() -> Path:
    """Return the path to the OpenCode database.

    Uses ``XDG_DATA_HOME`` if set, otherwise defaults to
    ``~/.local/share/opencode/opencode.db``.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "opencode" / DB_FILENAME
    return Path.home() / ".local" / "share" / "opencode" / DB_FILENAME


def _millis_to_iso(ts: int | None) -> str | None:
    """Convert a Unix timestamp in milliseconds to an ISO 8601 string."""
    if ts is None or ts == 0:
        return None
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()


def _extract_text_from_parts(conn: sqlite3.Connection, message_id: str) -> tuple[str, str | None]:
    """Extract text content from parts for a given message.

    Returns:
        (text_content, thinking_content)

    Note: OpenCode does not currently expose separate "thinking" content
    in the same way as Claude. All text parts are combined into text_content.
    """
    texts: list[str] = []

    try:
        cursor = conn.execute(
            "SELECT data FROM part WHERE message_id = ? ORDER BY time_created ASC",
            (message_id,),
        )
        for (data_json,) in cursor:
            try:
                part = json.loads(data_json)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(part, dict):
                continue

            part_type = part.get("type", "")
            if part_type == "text":
                text = part.get("text", "")
                if text:
                    texts.append(text)
    except Exception:
        pass

    text_content = "\n".join(texts)
    return text_content, None


def list_opencode_sessions(
    directory: str | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Discover OpenCode sessions.

    Reads from the centralized OpenCode database at
    ``~/.local/share/opencode/opencode.db`` and returns session summaries.

    Args:
        directory: Filter to sessions for this specific project directory.
        limit: Maximum sessions to return.

    Returns:
        List of session summaries sorted by last_activity descending.
    """
    db_path = _opencode_db_path()
    if not db_path.exists():
        return []

    running_sessions = find_running_opencode_sessions()
    sessions: list[SessionSummary] = []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        try:
            # Build query with optional directory filter
            query = """
                SELECT id, directory, title, time_created, time_updated
                FROM session
                WHERE parent_id IS NULL
            """
            params = []

            if directory:
                query += " AND directory = ?"
                params.append(directory)

            query += " ORDER BY time_updated DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor = conn.execute(query, params)

            for row in cursor:
                session_id = row["id"]
                session_dir = row["directory"]
                title = row["title"]
                time_updated = row["time_updated"]
                last_activity = _millis_to_iso(time_updated) or ""

                # Get first and last user prompts
                first_prompt, last_prompt = _get_first_last_prompts(conn, session_id)

                # Use title as fallback for first_prompt
                if not first_prompt and title:
                    first_prompt = title[:200]

                # Count messages (user + assistant)
                message_count_cursor = conn.execute(
                    "SELECT COUNT(*) FROM message WHERE session_id = ?",
                    (session_id,),
                )
                message_count = message_count_cursor.fetchone()[0]

                sessions.append(
                    SessionSummary(
                        id=session_id,
                        runner_type=RunnerType.OPENCODE,
                        directory=session_dir,
                        first_prompt=first_prompt,
                        last_prompt=last_prompt,
                        last_activity=last_activity,
                        message_count=message_count,
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

    return sessions


def _get_first_last_prompts(
    conn: sqlite3.Connection, session_id: str
) -> tuple[str | None, str | None]:
    """Get the first and last user prompts for a session."""
    first_prompt: str | None = None
    last_prompt: str | None = None

    try:
        # Get user messages ordered by creation time
        cursor = conn.execute(
            """
            SELECT id, data FROM message
            WHERE session_id = ? AND json_extract(data, '$.role') = 'user'
            ORDER BY time_created ASC
            """,
            (session_id,),
        )

        for message_id, data_json in cursor:
            # Extract text from parts
            text, _ = _extract_text_from_parts(conn, message_id)
            if text:
                prompt = text[:200]
                if first_prompt is None:
                    first_prompt = prompt
                last_prompt = prompt
    except Exception:
        pass

    return first_prompt, last_prompt


def get_opencode_session_detail(
    session_id: str,
    limit: int = 100,
) -> SessionDetail | None:
    """Load full message history for an OpenCode session.

    Args:
        session_id: The session ID.
        limit: Maximum messages to return.

    Returns:
        Session detail with messages, or None if not found.
    """
    db_path = _opencode_db_path()
    if not db_path.exists():
        return None

    running_sessions = find_running_opencode_sessions()

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        try:
            # Get session info
            cursor = conn.execute(
                "SELECT id, directory, title, time_created, time_updated "
                "FROM session WHERE id = ? LIMIT 1",
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            session_dir = row["directory"]
            title = row["title"]
            time_updated = row["time_updated"]
            last_activity = _millis_to_iso(time_updated) or ""

            # Get first and last prompts
            first_prompt, last_prompt = _get_first_last_prompts(conn, session_id)
            if not first_prompt and title:
                first_prompt = title[:200]

            # Get messages
            messages = _get_messages(conn, session_id, limit=limit)

            return SessionDetail(
                id=session_id,
                runner_type=RunnerType.OPENCODE,
                directory=session_dir,
                first_prompt=first_prompt,
                last_prompt=last_prompt,
                last_activity=last_activity,
                message_count=len(messages),
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


def _get_messages(
    conn: sqlite3.Connection, session_id: str, limit: int = 100
) -> list[SessionMessage]:
    """Get messages for a session, applying the limit to the most recent."""
    messages: list[SessionMessage] = []

    try:
        cursor = conn.execute(
            "SELECT id, data, time_created FROM message "
            "WHERE session_id = ? ORDER BY time_created ASC",
            (session_id,),
        )
        all_rows = cursor.fetchall()

        # Apply limit to most recent
        if len(all_rows) > limit:
            all_rows = all_rows[-limit:]

        for row in all_rows:
            message_id = row["id"]
            data_json = row["data"]
            time_created = row["time_created"]
            timestamp = _millis_to_iso(time_created)

            try:
                data = json.loads(data_json)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(data, dict):
                continue

            role = data.get("role")
            if role not in ("user", "assistant"):
                continue

            # Extract text from parts
            text, thinking = _extract_text_from_parts(conn, message_id)

            if text or thinking:
                messages.append(
                    SessionMessage(
                        role=role,
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
