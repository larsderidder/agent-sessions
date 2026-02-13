"""Data models for discovered agent sessions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class RunnerType(str, Enum):
    """Types of agent session sources."""

    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    PI = "pi"


class SessionMessage(BaseModel):
    """Normalized message from session history."""

    role: str  # "user" or "assistant"
    content: str
    thinking: str | None = None
    timestamp: str | None = None


class SessionSummary(BaseModel):
    """Summary info for a discovered session (for list views)."""

    id: str
    runner_type: RunnerType
    directory: str
    first_prompt: str | None = None
    last_prompt: str | None = None
    last_activity: str
    message_count: int
    is_running: bool


class SessionDetail(SessionSummary):
    """Full session with message history."""

    messages: list[SessionMessage] = []
