"""Tests for OpenCode session discovery."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from agent_sessions.providers.opencode import (
    list_opencode_sessions,
    get_opencode_session_detail,
    _extract_text_parts,
    _extract_user_prompt,
    _find_databases,
    _directory_from_db_path,
)
from agent_sessions.models import RunnerType


def _create_opencode_db(db_path: Path) -> None:
    """Create an OpenCode SQLite database with schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            parent_session_id TEXT,
            title TEXT NOT NULL,
            message_count INTEGER NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0.0,
            summary_message_id TEXT,
            updated_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
        """)
    conn.execute("""
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            parts TEXT NOT NULL DEFAULT '[]',
            model TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            finished_at INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
        )
        """)
    conn.commit()
    conn.close()


def _insert_session(
    db_path: Path,
    session_id: str,
    title: str = "Test Session",
    message_count: int = 0,
    parent_session_id: str | None = None,
    created_at: int = 1700000000,
    updated_at: int = 1700000100,
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO sessions (id, parent_session_id, title, message_count, "
        "prompt_tokens, completion_tokens, cost, updated_at, created_at) "
        "VALUES (?, ?, ?, ?, 0, 0, 0.0, ?, ?)",
        (session_id, parent_session_id, title, message_count, updated_at, created_at),
    )
    conn.commit()
    conn.close()


def _insert_message(
    db_path: Path,
    message_id: str,
    session_id: str,
    role: str,
    parts: list[dict],
    created_at: int = 1700000050,
) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO messages (id, session_id, role, parts, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, session_id, role, json.dumps(parts), created_at, created_at),
    )
    conn.commit()
    conn.close()


# --- Unit tests for helpers ---


def test_extract_text_parts():
    parts = json.dumps(
        [
            {"type": "text", "data": {"text": "Hello world"}},
            {"type": "reasoning", "data": {"thinking": "Let me think"}},
        ]
    )
    text, thinking = _extract_text_parts(parts)
    assert text == "Hello world"
    assert thinking == "Let me think"


def test_extract_text_parts_no_thinking():
    parts = json.dumps([{"type": "text", "data": {"text": "Just text"}}])
    text, thinking = _extract_text_parts(parts)
    assert text == "Just text"
    assert thinking is None


def test_extract_text_parts_empty():
    text, thinking = _extract_text_parts("[]")
    assert text == ""
    assert thinking is None


def test_extract_text_parts_invalid_json():
    text, thinking = _extract_text_parts("not json")
    assert text == ""
    assert thinking is None


def test_extract_user_prompt():
    parts = json.dumps([{"type": "text", "data": {"text": "Write a function"}}])
    assert _extract_user_prompt(parts) == "Write a function"


def test_extract_user_prompt_tool_result():
    parts = json.dumps([{"type": "tool_result", "data": {"content": "file contents..."}}])
    assert _extract_user_prompt(parts) is None


def test_extract_user_prompt_empty():
    assert _extract_user_prompt("[]") is None


def test_directory_from_db_path():
    path = Path("/home/lars/myproject/.opencode/opencode.db")
    assert _directory_from_db_path(path) == "/home/lars/myproject"


# --- find_databases ---


def test_find_databases(tmp_path: Path) -> None:
    # Create two project databases
    db1 = tmp_path / "project-a" / ".opencode" / "opencode.db"
    db2 = tmp_path / "project-b" / ".opencode" / "opencode.db"
    _create_opencode_db(db1)
    _create_opencode_db(db2)

    # Create a nested project (should also be found)
    db3 = tmp_path / "workspace" / "project-c" / ".opencode" / "opencode.db"
    _create_opencode_db(db3)

    found = _find_databases([tmp_path])
    found_strs = {str(p) for p in found}
    assert str(db1) in found_strs
    assert str(db2) in found_strs
    assert str(db3) in found_strs


def test_find_databases_skips_hidden_dirs(tmp_path: Path) -> None:
    # Hidden directory should be skipped
    db = tmp_path / ".hidden" / "project" / ".opencode" / "opencode.db"
    _create_opencode_db(db)

    found = _find_databases([tmp_path])
    assert len(found) == 0


def test_find_databases_skips_node_modules(tmp_path: Path) -> None:
    db = tmp_path / "node_modules" / "pkg" / ".opencode" / "opencode.db"
    _create_opencode_db(db)

    found = _find_databases([tmp_path])
    assert len(found) == 0


# --- list_opencode_sessions ---


def test_list_opencode_sessions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    db_path = tmp_path / "myproject" / ".opencode" / "opencode.db"
    _create_opencode_db(db_path)

    session_id = "abc123-def456-7890"
    _insert_session(db_path, session_id, title="Fix bug", message_count=3, updated_at=1700000200)
    _insert_message(
        db_path,
        "msg1",
        session_id,
        "user",
        [{"type": "text", "data": {"text": "Fix the login bug"}}],
        created_at=1700000050,
    )
    _insert_message(
        db_path,
        "msg2",
        session_id,
        "assistant",
        [
            {"type": "reasoning", "data": {"thinking": "Looking at the code"}},
            {"type": "text", "data": {"text": "I found the issue in auth.py"}},
        ],
        created_at=1700000060,
    )

    sessions = list_opencode_sessions()
    assert len(sessions) == 1
    s = sessions[0]
    assert s.id == session_id
    assert s.runner_type == RunnerType.OPENCODE
    assert s.directory == str(tmp_path / "myproject")
    assert s.first_prompt == "Fix the login bug"
    assert s.message_count == 3
    assert s.is_running is False


def test_list_opencode_sessions_directory_filter(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    # Create two projects
    db1 = tmp_path / "project-a" / ".opencode" / "opencode.db"
    db2 = tmp_path / "project-b" / ".opencode" / "opencode.db"
    _create_opencode_db(db1)
    _create_opencode_db(db2)

    _insert_session(db1, "s1", title="Session A", message_count=1, updated_at=1700000100)
    _insert_session(db2, "s2", title="Session B", message_count=2, updated_at=1700000200)

    # Filter to project-a
    sessions = list_opencode_sessions(directory=str(tmp_path / "project-a"))
    assert len(sessions) == 1
    assert sessions[0].id == "s1"


def test_list_opencode_sessions_excludes_child_sessions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    db_path = tmp_path / "myproject" / ".opencode" / "opencode.db"
    _create_opencode_db(db_path)

    _insert_session(db_path, "parent", title="Main session", message_count=5)
    _insert_session(
        db_path, "child", title="Generate title", parent_session_id="parent", message_count=1
    )

    sessions = list_opencode_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == "parent"


def test_list_opencode_sessions_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path / "nonexistent"))
    sessions = list_opencode_sessions()
    assert sessions == []


def test_list_opencode_sessions_title_fallback(monkeypatch, tmp_path: Path) -> None:
    """When there are no user messages, title is used as first_prompt."""
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    db_path = tmp_path / "myproject" / ".opencode" / "opencode.db"
    _create_opencode_db(db_path)

    _insert_session(db_path, "s1", title="My Title", message_count=0)

    sessions = list_opencode_sessions()
    assert len(sessions) == 1
    assert sessions[0].first_prompt == "My Title"


# --- get_opencode_session_detail ---


def test_get_opencode_session_detail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    db_path = tmp_path / "myproject" / ".opencode" / "opencode.db"
    _create_opencode_db(db_path)

    session_id = "detail-session-001"
    _insert_session(db_path, session_id, title="Detail test", message_count=3)

    _insert_message(
        db_path,
        "m1",
        session_id,
        "user",
        [{"type": "text", "data": {"text": "Hello OpenCode"}}],
        created_at=1700000010,
    )
    _insert_message(
        db_path,
        "m2",
        session_id,
        "assistant",
        [
            {"type": "reasoning", "data": {"thinking": "Greeting the user"}},
            {"type": "text", "data": {"text": "Hi! How can I help?"}},
        ],
        created_at=1700000020,
    )
    _insert_message(
        db_path,
        "m3",
        session_id,
        "user",
        [{"type": "text", "data": {"text": "List files"}}],
        created_at=1700000030,
    )

    detail = get_opencode_session_detail(session_id)
    assert detail is not None
    assert detail.id == session_id
    assert detail.runner_type == RunnerType.OPENCODE
    assert detail.directory == str(tmp_path / "myproject")
    assert detail.first_prompt == "Hello OpenCode"
    assert detail.last_prompt == "List files"
    assert len(detail.messages) == 3
    assert detail.messages[0].role == "user"
    assert detail.messages[0].content == "Hello OpenCode"
    assert detail.messages[1].role == "assistant"
    assert detail.messages[1].content == "Hi! How can I help?"
    assert detail.messages[1].thinking == "Greeting the user"
    assert detail.messages[2].role == "user"
    assert detail.messages[2].content == "List files"


def test_get_opencode_session_detail_not_found(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    # Create an empty DB
    db_path = tmp_path / "myproject" / ".opencode" / "opencode.db"
    _create_opencode_db(db_path)

    assert get_opencode_session_detail("nonexistent") is None


def test_get_opencode_session_detail_message_limit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENCODE_SEARCH_DIRS", str(tmp_path))
    monkeypatch.setattr(
        "agent_sessions.providers.opencode.find_running_opencode_sessions",
        lambda: set(),
    )

    db_path = tmp_path / "myproject" / ".opencode" / "opencode.db"
    _create_opencode_db(db_path)

    session_id = "limit-test"
    _insert_session(db_path, session_id, title="Limit test", message_count=10)

    for i in range(10):
        _insert_message(
            db_path,
            f"m{i}",
            session_id,
            "user",
            [{"type": "text", "data": {"text": f"Message {i}"}}],
            created_at=1700000000 + i,
        )

    detail = get_opencode_session_detail(session_id, limit=3)
    assert detail is not None
    assert len(detail.messages) == 3
    # Should be the last 3 messages
    assert detail.messages[0].content == "Message 7"
    assert detail.messages[2].content == "Message 9"
