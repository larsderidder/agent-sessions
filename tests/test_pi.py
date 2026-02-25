"""Tests for Pi session discovery."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.providers.pi import (
    list_pi_sessions,
    get_pi_session_detail,
    get_pi_session_model,
    _decode_directory_name,
    _encode_directory_name,
)


def _write_pi_session(path: Path, session_id: str, cwd: str = "/home/lars/project") -> None:
    records = [
        {
            "type": "session",
            "version": 3,
            "id": session_id,
            "timestamp": "2026-02-11T08:00:00.000Z",
            "cwd": cwd,
        },
        {
            "type": "message",
            "id": "msg1",
            "parentId": "model1",
            "timestamp": "2026-02-11T08:01:00.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello pi"}],
            },
        },
        {
            "type": "message",
            "id": "msg2",
            "parentId": "msg1",
            "timestamp": "2026-02-11T08:01:10.000Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "User is greeting me"},
                    {"type": "text", "text": "Hello! How can I help?"},
                ],
            },
        },
        {
            "type": "message",
            "id": "msg3",
            "parentId": "msg2",
            "timestamp": "2026-02-11T08:02:00.000Z",
            "message": {
                "role": "user",
                "content": "What files are here?",
            },
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def test_decode_directory_name():
    assert _decode_directory_name("--home-lars-project--") == "/home/lars/project"


def test_encode_directory_name():
    assert _encode_directory_name("/home/lars/project") == "--home-lars-project--"


def test_roundtrip_directory_encoding():
    for path in ["/home/lars/project", "/tmp/test"]:
        assert _decode_directory_name(_encode_directory_name(path)) == path


def test_list_pi_sessions(monkeypatch, tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setenv("PI_SESSIONS_DIR", str(sessions_dir))
    monkeypatch.setattr("agent_sessions.providers.pi.find_running_pi_sessions", lambda: set())

    session_id = "d6660987-06ac-427d-b751-1232e8b88ca2"
    project_dir = sessions_dir / "--home-lars-project--"
    session_file = project_dir / f"2026-02-11T08-00-00-000Z_{session_id}.jsonl"
    _write_pi_session(session_file, session_id)

    sessions = list_pi_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == session_id
    assert sessions[0].first_prompt == "Hello pi"
    assert sessions[0].message_count == 3
    assert sessions[0].directory == "/home/lars/project"
    assert sessions[0].runner_type.value == "pi"
    assert sessions[0].is_running is False


def test_list_pi_sessions_filtered(monkeypatch, tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setenv("PI_SESSIONS_DIR", str(sessions_dir))
    monkeypatch.setattr("agent_sessions.providers.pi.find_running_pi_sessions", lambda: set())

    session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    project_dir = sessions_dir / "--home-lars-project--"
    session_file = project_dir / f"2026-02-11T08-00-00-000Z_{session_id}.jsonl"
    _write_pi_session(session_file, session_id)

    assert len(list_pi_sessions(directory="/home/lars/other")) == 0
    assert len(list_pi_sessions(directory="/home/lars/project")) == 1


def test_get_pi_session_detail(monkeypatch, tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setenv("PI_SESSIONS_DIR", str(sessions_dir))
    monkeypatch.setattr("agent_sessions.providers.pi.find_running_pi_sessions", lambda: set())

    session_id = "d6660987-06ac-427d-b751-1232e8b88ca2"
    project_dir = sessions_dir / "--home-lars-project--"
    session_file = project_dir / f"2026-02-11T08-00-00-000Z_{session_id}.jsonl"
    _write_pi_session(session_file, session_id)

    detail = get_pi_session_detail(session_id)
    assert detail is not None
    assert detail.id == session_id
    assert detail.directory == "/home/lars/project"
    assert [m.role for m in detail.messages] == ["user", "assistant", "user"]
    assert detail.messages[0].content == "Hello pi"
    assert detail.messages[1].thinking == "User is greeting me"
    assert detail.messages[2].content == "What files are here?"


def test_get_pi_session_detail_not_found(monkeypatch, tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".pi" / "agent" / "sessions"
    monkeypatch.setenv("PI_SESSIONS_DIR", str(sessions_dir))
    sessions_dir.mkdir(parents=True, exist_ok=True)
    assert get_pi_session_detail("nonexistent") is None


def test_list_pi_sessions_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PI_SESSIONS_DIR", str(tmp_path / "nonexistent"))
    assert list_pi_sessions() == []


def _write_pi_session_with_model_changes(
    path: Path,
    session_id: str,
    cwd: str = "/home/lars/project",
) -> None:
    """Write a pi session file with model_change records and messages."""
    records = [
        {
            "type": "session",
            "version": 3,
            "id": session_id,
            "timestamp": "2026-02-11T08:00:00.000Z",
            "cwd": cwd,
        },
        # Initial model set at session start
        {
            "type": "model_change",
            "id": "model1",
            "parentId": None,
            "timestamp": "2026-02-11T08:00:00.001Z",
            "provider": "anthropic",
            "modelId": "claude-sonnet-4-6",
        },
        {
            "type": "message",
            "id": "msg1",
            "parentId": "model1",
            "timestamp": "2026-02-11T08:01:00.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}],
            },
        },
        {
            "type": "message",
            "id": "msg2",
            "parentId": "msg1",
            "timestamp": "2026-02-11T08:01:10.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hi there!"}],
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
            },
        },
        # User switched to a different model mid-session
        {
            "type": "model_change",
            "id": "model2",
            "parentId": "msg2",
            "timestamp": "2026-02-11T08:02:00.000Z",
            "provider": "anthropic",
            "modelId": "claude-opus-4-6",
        },
        {
            "type": "message",
            "id": "msg3",
            "parentId": "model2",
            "timestamp": "2026-02-11T08:02:10.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Now use opus"}],
            },
        },
        {
            "type": "message",
            "id": "msg4",
            "parentId": "msg3",
            "timestamp": "2026-02-11T08:02:20.000Z",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Using opus!"}],
                "provider": "anthropic",
                "model": "claude-opus-4-6",
            },
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def test_get_pi_session_model_reads_last_model_change(tmp_path: Path) -> None:
    """get_pi_session_model returns the last model used in the session tree."""
    session_id = "aaaaaaaa-0000-0000-0000-000000000001"
    session_file = tmp_path / f"2026-02-11T08-00-00-000Z_{session_id}.jsonl"
    _write_pi_session_with_model_changes(session_file, session_id)

    result = get_pi_session_model(session_file)
    assert result == ("anthropic", "claude-opus-4-6")


def test_get_pi_session_model_no_model_change(tmp_path: Path) -> None:
    """get_pi_session_model returns None when no model info is present."""
    session_id = "aaaaaaaa-0000-0000-0000-000000000002"
    session_file = tmp_path / f"2026-02-11T08-00-00-000Z_{session_id}.jsonl"
    # Write a session with only a header (no model_change, no messages with provider)
    records = [
        {
            "type": "session",
            "version": 3,
            "id": session_id,
            "timestamp": "2026-02-11T08:00:00.000Z",
            "cwd": "/home/lars/project",
        }
    ]
    session_file.parent.mkdir(parents=True, exist_ok=True)
    with session_file.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    result = get_pi_session_model(session_file)
    assert result is None


def test_get_pi_session_model_single_model_change(tmp_path: Path) -> None:
    """get_pi_session_model works with a single model_change at the root."""
    session_id = "aaaaaaaa-0000-0000-0000-000000000003"
    session_file = tmp_path / f"2026-02-11T08-00-00-000Z_{session_id}.jsonl"
    records = [
        {
            "type": "session",
            "version": 3,
            "id": session_id,
            "timestamp": "2026-02-11T08:00:00.000Z",
            "cwd": "/home/lars/project",
        },
        {
            "type": "model_change",
            "id": "model1",
            "parentId": None,
            "timestamp": "2026-02-11T08:00:00.001Z",
            "provider": "anthropic",
            "modelId": "claude-sonnet-4-6",
        },
        {
            "type": "message",
            "id": "msg1",
            "parentId": "model1",
            "timestamp": "2026-02-11T08:01:00.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello"}],
            },
        },
    ]
    session_file.parent.mkdir(parents=True, exist_ok=True)
    with session_file.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    result = get_pi_session_model(session_file)
    assert result == ("anthropic", "claude-sonnet-4-6")
