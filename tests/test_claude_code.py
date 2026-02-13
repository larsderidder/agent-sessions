"""Tests for Claude Code session discovery."""

from __future__ import annotations

import json
from pathlib import Path

from agent_sessions.providers.claude_code import (
    list_claude_sessions,
    get_claude_session_detail,
    encode_project_path,
    decode_project_path,
)


def _write_session(path: Path, session_id: str) -> None:
    records = [
        {
            "type": "summary",
            "summary": "Session summary",
            "leafId": session_id,
            "userMessages": 2,
            "assistantMessages": 2,
        },
        {
            "parentMessageId": "",
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Hello Claude"}],
            },
            "uuid": "msg-1",
            "timestamp": "2026-02-10T12:00:00.000Z",
        },
        {
            "parentMessageId": "msg-1",
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello! How can I help?"}],
            },
            "uuid": "msg-2",
            "timestamp": "2026-02-10T12:00:05.000Z",
        },
        {
            "parentMessageId": "msg-2",
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "What's this project about?"}],
            },
            "uuid": "msg-3",
            "timestamp": "2026-02-10T12:01:00.000Z",
        },
        {
            "parentMessageId": "msg-3",
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Let me take a look..."}],
            },
            "uuid": "msg-4",
            "timestamp": "2026-02-10T12:01:10.000Z",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def test_encode_project_path():
    assert encode_project_path("/home/lars/project") == "-home-lars-project"


def test_decode_project_path():
    assert decode_project_path("-home-lars-project") == "/home/lars/project"


def test_roundtrip():
    for p in ["/home/user/code", "/tmp/test"]:
        assert decode_project_path(encode_project_path(p)) == p


def test_list_claude_sessions(monkeypatch, tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(
        "agent_sessions.providers.claude_code.PROJECTS_DIR", projects_dir
    )

    session_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    project_dir = projects_dir / encode_project_path("/home/lars/myproject")
    session_file = project_dir / f"{session_id}.jsonl"
    _write_session(session_file, session_id)

    sessions = list_claude_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == session_id
    assert sessions[0].first_prompt == "Hello Claude"
    assert sessions[0].message_count == 4
    assert sessions[0].runner_type.value == "claude_code"


def test_get_claude_session_detail(monkeypatch, tmp_path: Path) -> None:
    projects_dir = tmp_path / "projects"
    monkeypatch.setattr(
        "agent_sessions.providers.claude_code.PROJECTS_DIR", projects_dir
    )

    session_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    project_dir = projects_dir / encode_project_path("/home/lars/myproject")
    session_file = project_dir / f"{session_id}.jsonl"
    _write_session(session_file, session_id)

    detail = get_claude_session_detail(session_id)
    assert detail is not None
    assert detail.id == session_id
    assert [m.role for m in detail.messages] == ["user", "assistant", "user", "assistant"]
    assert detail.messages[0].content == "Hello Claude"
    assert detail.messages[1].content == "Hello! How can I help?"


def test_list_claude_sessions_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "agent_sessions.providers.claude_code.PROJECTS_DIR", tmp_path / "nonexistent"
    )
    assert list_claude_sessions() == []
