"""Tests for OpenCode session discovery."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agent_sessions.providers.opencode import (
    list_opencode_sessions,
    get_opencode_session_detail,
    _extract_text_from_parts,
    _millis_to_iso,
)
from agent_sessions.models import RunnerType


def _create_opencode_db(db_path: Path) -> None:
    """Create an OpenCode SQLite database with the current schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))

    # Create tables matching OpenCode 1.2.5 schema
    conn.execute("""
        CREATE TABLE session (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            parent_id TEXT,
            slug TEXT NOT NULL,
            directory TEXT NOT NULL,
            title TEXT NOT NULL,
            version TEXT NOT NULL,
            share_url TEXT,
            summary_additions INTEGER,
            summary_deletions INTEGER,
            summary_files INTEGER,
            summary_diffs TEXT,
            revert TEXT,
            permission TEXT,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            time_compacting INTEGER,
            time_archived INTEGER
        )
        """)

    conn.execute("""
        CREATE TABLE message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
        """)

    conn.execute("""
        CREATE TABLE part (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            time_created INTEGER NOT NULL,
            time_updated INTEGER NOT NULL,
            data TEXT NOT NULL
        )
        """)

    conn.commit()
    conn.close()


def _insert_session(
    db_path: Path,
    session_id: str,
    directory: str,
    title: str = "Test Session",
    parent_id: str | None = None,
    time_created: int = 1700000000000,
    time_updated: int = 1700000100000,
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO session (id, project_id, parent_id, slug, directory, title, "
        "version, time_created, time_updated) "
        "VALUES (?, 'proj1', ?, 'test', ?, ?, '1.0', ?, ?)",
        (session_id, parent_id, directory, title, time_created, time_updated),
    )
    conn.commit()
    conn.close()


def _insert_message(
    db_path: Path,
    message_id: str,
    session_id: str,
    role: str,
    parts: list[dict],
    time_created: int = 1700000050000,
) -> None:
    conn = sqlite3.connect(str(db_path))

    # Insert message metadata
    data = {"role": role}
    conn.execute(
        "INSERT INTO message (id, session_id, time_created, time_updated, data) "
        "VALUES (?, ?, ?, ?, ?)",
        (message_id, session_id, time_created, time_created, json.dumps(data)),
    )

    # Insert parts
    for i, part in enumerate(parts):
        part_id = f"{message_id}_p{i}"
        conn.execute(
            "INSERT INTO part (id, message_id, session_id, time_created, time_updated, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                part_id,
                message_id,
                session_id,
                time_created + i,
                time_created + i,
                json.dumps(part),
            ),
        )

    conn.commit()
    conn.close()


# --- Unit tests for helpers ---


def test_millis_to_iso():
    assert _millis_to_iso(1700000000000) == "2023-11-14T22:13:20+00:00"
    assert _millis_to_iso(0) is None
    assert _millis_to_iso(None) is None


def test_extract_text_from_parts(tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    _create_opencode_db(db_path)

    # Insert a message with parts
    _insert_message(
        db_path,
        "msg1",
        "ses1",
        "user",
        [
            {"type": "text", "text": "Hello world"},
            {"type": "step-start", "snapshot": "abc123"},
        ],
        time_created=1700000000000,
    )

    conn = sqlite3.connect(str(db_path))
    text, thinking = _extract_text_from_parts(conn, "msg1")
    conn.close()

    assert text == "Hello world"
    assert thinking is None


# --- list_opencode_sessions ---


def test_list_opencode_sessions(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    _create_opencode_db(db_path)

    session_id = "ses_abc123"
    _insert_session(
        db_path,
        session_id,
        directory="/home/user/myproject",
        title="Fix bug",
        time_created=1700000000000,
        time_updated=1700000200000,
    )
    _insert_message(
        db_path,
        "msg1",
        session_id,
        "user",
        [{"type": "text", "text": "Fix the login bug"}],
        time_created=1700000050000,
    )
    _insert_message(
        db_path,
        "msg2",
        session_id,
        "assistant",
        [{"type": "text", "text": "I found the issue in auth.py"}],
        time_created=1700000060000,
    )

    sessions = list_opencode_sessions()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.id == session_id
    assert s.runner_type == RunnerType.OPENCODE
    assert s.directory == "/home/user/myproject"
    assert s.first_prompt == "Fix the login bug"
    assert s.last_prompt == "Fix the login bug"
    assert s.message_count == 2
    assert s.is_running is False


def test_list_opencode_sessions_directory_filter(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    _create_opencode_db(db_path)

    _insert_session(
        db_path,
        "s1",
        directory="/home/user/project-a",
        title="Session A",
        time_updated=1700000100000,
    )
    _insert_session(
        db_path,
        "s2",
        directory="/home/user/project-b",
        title="Session B",
        time_updated=1700000200000,
    )

    # Filter to project-a
    sessions = list_opencode_sessions(directory="/home/user/project-a")
    assert len(sessions) == 1
    assert sessions[0].id == "s1"


def test_list_opencode_sessions_excludes_child_sessions(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    _create_opencode_db(db_path)

    _insert_session(db_path, "parent", directory="/home/user/proj", title="Main session")
    _insert_session(
        db_path,
        "child",
        directory="/home/user/proj",
        title="Generate title",
        parent_id="parent",
    )

    sessions = list_opencode_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == "parent"


def test_list_opencode_sessions_empty(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "nonexistent" / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    sessions = list_opencode_sessions()
    assert sessions == []


def test_list_opencode_sessions_title_fallback(monkeypatch, tmp_path: Path):
    """When there are no user messages, title is used as first_prompt."""
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    _create_opencode_db(db_path)
    _insert_session(db_path, "s1", directory="/tmp", title="My Title")

    sessions = list_opencode_sessions()
    assert len(sessions) == 1
    assert sessions[0].first_prompt == "My Title"


# --- get_opencode_session_detail ---


def test_get_opencode_session_detail(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    _create_opencode_db(db_path)

    session_id = "detail-session-001"
    _insert_session(db_path, session_id, directory="/home/user/myproject", title="Detail test")

    _insert_message(
        db_path,
        "m1",
        session_id,
        "user",
        [{"type": "text", "text": "Hello OpenCode"}],
        time_created=1700000010000,
    )
    _insert_message(
        db_path,
        "m2",
        session_id,
        "assistant",
        [{"type": "text", "text": "Hi! How can I help?"}],
        time_created=1700000020000,
    )
    _insert_message(
        db_path,
        "m3",
        session_id,
        "user",
        [{"type": "text", "text": "List files"}],
        time_created=1700000030000,
    )

    detail = get_opencode_session_detail(session_id)
    assert detail is not None
    assert detail.id == session_id
    assert detail.runner_type == RunnerType.OPENCODE
    assert detail.directory == "/home/user/myproject"
    assert detail.first_prompt == "Hello OpenCode"
    assert detail.last_prompt == "List files"
    assert len(detail.messages) == 3
    assert detail.messages[0].role == "user"
    assert detail.messages[0].content == "Hello OpenCode"
    assert detail.messages[1].role == "assistant"
    assert detail.messages[1].content == "Hi! How can I help?"
    assert detail.messages[2].role == "user"
    assert detail.messages[2].content == "List files"


def test_get_opencode_session_detail_not_found(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)

    _create_opencode_db(db_path)
    assert get_opencode_session_detail("nonexistent") is None


def test_get_opencode_session_detail_message_limit(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "opencode.db"
    monkeypatch.setattr("agent_sessions.providers.opencode._opencode_db_path", lambda: db_path)
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    _create_opencode_db(db_path)

    session_id = "limit-test"
    _insert_session(db_path, session_id, directory="/tmp", title="Limit test")

    for i in range(10):
        _insert_message(
            db_path,
            f"m{i}",
            session_id,
            "user",
            [{"type": "text", "text": f"Message {i}"}],
            time_created=1700000000000 + i,
        )

    detail = get_opencode_session_detail(session_id, limit=3)
    assert detail is not None
    assert len(detail.messages) == 3
    # Should be the last 3 messages
    assert detail.messages[0].content == "Message 7"
    assert detail.messages[2].content == "Message 9"
