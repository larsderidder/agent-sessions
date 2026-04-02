from __future__ import annotations

import json

from agent_sessions.cli import main
from agent_sessions.models import RunnerType, SessionDetail, SessionMessage, SessionSummary


def test_list_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "agent_sessions.cli.discover_sessions",
        lambda **_: [
            SessionSummary(
                id="abc123",
                runner_type=RunnerType.CODEX,
                directory="/tmp/demo",
                first_prompt="hello",
                last_prompt="hello",
                last_activity="2026-04-02T00:00:00Z",
                message_count=2,
                is_running=False,
            )
        ],
    )

    assert main(["list", "--runner-type", "codex", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["id"] == "abc123"
    assert payload[0]["runner_type"] == "codex"


def test_show_not_found(monkeypatch, capsys) -> None:
    monkeypatch.setattr("agent_sessions.cli.get_session_detail", lambda **_: None)

    assert main(["show", "missing", "--runner-type", "codex"]) == 1
    assert "missing" in capsys.readouterr().err


def test_show_human_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "agent_sessions.cli.get_session_detail",
        lambda **_: SessionDetail(
            id="abc123",
            runner_type=RunnerType.CODEX,
            directory="/tmp/demo",
            first_prompt="hello",
            last_prompt="hello",
            last_activity="2026-04-02T00:00:00Z",
            message_count=1,
            is_running=True,
            messages=[
                SessionMessage(
                    role="user",
                    content="Hello Codex",
                    timestamp="2026-04-02T00:00:00Z",
                )
            ],
        ),
    )

    assert main(["show", "abc123", "--runner-type", "codex"]) == 0
    out = capsys.readouterr().out
    assert "Hello Codex" in out
    assert "Running: yes" in out
