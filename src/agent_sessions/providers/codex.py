"""Codex session discovery and parsing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import json
import os
import re
from pathlib import Path
import sqlite3

import logging

from agent_sessions.running import find_running_codex_sessions
from agent_sessions.path_utils import normalize_directory_path
from agent_sessions.models import (
    RunnerType,
    SessionSummary,
    SessionDetail,
    SessionMessage,
)

logger = logging.getLogger(__name__)

_ROLLOUT_ID_RE = re.compile(r"rollout-.*-([0-9a-fA-F-]{32,})\.jsonl$")


@dataclass(frozen=True)
class _SqliteThreadRecord:
    """Minimal Codex thread metadata available before rollout files exist."""

    session_id: str
    rollout_path: Path | None
    created_at: int | None
    updated_at: int | None
    directory: str
    title: str | None
    first_user_message: str | None


def _codex_home() -> Path:
    """Resolve CODEX_HOME, defaulting to ~/.codex."""
    value = os.environ.get("CODEX_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".codex"


def _sessions_dir() -> Path:
    return _codex_home() / "sessions"


def _state_db_paths() -> tuple[Path, ...]:
    """Return readable Codex state databases ordered newest first."""
    home = _codex_home()
    candidates = sorted(
        (path for path in home.glob("state_*.sqlite") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return tuple(candidates)


def _sqlite_timestamp(value: object) -> str | None:
    """Convert a sqlite epoch value into an ISO timestamp."""
    if value is None:
        return None
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _sqlite_thread_records() -> list[_SqliteThreadRecord]:
    """Load Codex thread metadata from sqlite state databases."""
    records_by_id: dict[str, _SqliteThreadRecord] = {}

    for db_path in _state_db_paths():
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT
                        id,
                        rollout_path,
                        created_at,
                        updated_at,
                        cwd,
                        title,
                        first_user_message
                    FROM threads
                    """
                )
                for row in rows:
                    session_id = row["id"]
                    directory = row["cwd"]
                    if not isinstance(session_id, str) or not isinstance(directory, str):
                        continue

                    rollout_path = row["rollout_path"]
                    record = _SqliteThreadRecord(
                        session_id=session_id,
                        rollout_path=Path(rollout_path) if isinstance(rollout_path, str) and rollout_path else None,
                        created_at=int(row["created_at"]) if row["created_at"] is not None else None,
                        updated_at=int(row["updated_at"]) if row["updated_at"] is not None else None,
                        directory=directory,
                        title=row["title"] if isinstance(row["title"], str) else None,
                        first_user_message=(
                            row["first_user_message"]
                            if isinstance(row["first_user_message"], str)
                            else None
                        ),
                    )
                    current = records_by_id.get(record.session_id)
                    if current is None or (record.updated_at or 0) >= (current.updated_at or 0):
                        records_by_id[record.session_id] = record
        except sqlite3.Error as exc:
            logger.warning(
                "Failed to read Codex sqlite state database",
                db_path=str(db_path),
                error=str(exc),
            )

    return sorted(
        records_by_id.values(),
        key=lambda record: record.updated_at or record.created_at or 0,
        reverse=True,
    )


def _build_sqlite_summary(
    record: _SqliteThreadRecord,
    running_sessions: set[str],
) -> SessionSummary:
    prompt = (record.first_user_message or "").strip() or (record.title or "").strip() or None
    last_activity = (
        _sqlite_timestamp(record.updated_at)
        or _sqlite_timestamp(record.created_at)
        or datetime.now(tz=timezone.utc).isoformat()
    )
    message_count = 1 if record.first_user_message else 0
    return SessionSummary(
        id=record.session_id,
        runner_type=RunnerType.CODEX,
        directory=record.directory,
        first_prompt=prompt,
        last_prompt=prompt,
        last_activity=last_activity,
        message_count=message_count,
        is_running=record.session_id in running_sessions,
    )


def _build_sqlite_detail(
    record: _SqliteThreadRecord,
    running_sessions: set[str],
) -> SessionDetail:
    summary = _build_sqlite_summary(record, running_sessions)
    messages: list[SessionMessage] = []
    if record.first_user_message:
        messages.append(
            SessionMessage(
                role="user",
                content=record.first_user_message,
                timestamp=_sqlite_timestamp(record.created_at),
            )
        )
    return SessionDetail(
        id=summary.id,
        runner_type=summary.runner_type,
        directory=summary.directory,
        first_prompt=summary.first_prompt,
        last_prompt=summary.last_prompt,
        last_activity=summary.last_activity,
        message_count=len(messages),
        is_running=summary.is_running,
        messages=messages,
    )


def _extract_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in ("input_text", "output_text", "text"):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def _is_environment_context(text: str) -> bool:
    return text.lstrip().startswith("<environment_context>")


def _infer_session_id(session_file: Path) -> str | None:
    match = _ROLLOUT_ID_RE.match(session_file.name)
    if match:
        return match.group(1)
    return None


def _parse_session_summary(
    session_file: Path,
    running_sessions: set[str],
) -> SessionSummary | None:
    session_id: str | None = None
    first_prompt: str | None = None
    last_prompt: str | None = None
    last_activity: str | None = None
    directory: str | None = None
    message_count = 0

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = record.get("timestamp")
                if timestamp:
                    last_activity = timestamp

                record_type = record.get("type")
                payload = record.get("payload", {})

                if record_type == "session_meta":
                    session_id = payload.get("id") or session_id
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str):
                        directory = cwd

                if record_type == "response_item" and isinstance(payload, dict):
                    if payload.get("type") == "message":
                        role = payload.get("role")
                        content = payload.get("content")
                        text = _extract_text(content)
                        if role in ("user", "assistant"):
                            message_count += 1
                        if role == "user" and text:
                            if not _is_environment_context(text):
                                if first_prompt is None:
                                    first_prompt = text[:200]
                                last_prompt = text[:200]

        if session_id is None:
            session_id = _infer_session_id(session_file)

        if directory is None:
            return None

        if last_activity is None:
            mtime = session_file.stat().st_mtime
            from datetime import datetime, timezone

            last_activity = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        return SessionSummary(
            id=session_id or session_file.stem,
            runner_type=RunnerType.CODEX,
            directory=directory,
            first_prompt=first_prompt,
            last_prompt=last_prompt,
            last_activity=last_activity,
            message_count=message_count,
            is_running=(session_id or "") in running_sessions,
        )
    except Exception as exc:
        logger.warning(
            "Failed to parse Codex session file",
            session_file=str(session_file),
            error=str(exc),
        )
        return None


def list_codex_sessions(
    directory: str | None = None,
    limit: int = 50,
) -> list[SessionSummary]:
    """Discover Codex sessions stored under ~/.codex/sessions and sqlite state."""
    sessions_root = _sessions_dir()

    normalized_directory = normalize_directory_path(directory) if directory else None
    running_sessions = find_running_codex_sessions()
    sessions_by_id: dict[str, SessionSummary] = {}

    if sessions_root.exists():
        for session_file in sessions_root.rglob("rollout-*.jsonl"):
            summary = _parse_session_summary(session_file, running_sessions)
            if not summary:
                continue
            if (
                normalized_directory
                and normalize_directory_path(summary.directory) != normalized_directory
            ):
                continue
            sessions_by_id[summary.id] = summary

    for record in _sqlite_thread_records():
        if normalized_directory and normalize_directory_path(record.directory) != normalized_directory:
            continue
        existing = sessions_by_id.get(record.session_id)
        if existing is None:
            sessions_by_id[record.session_id] = _build_sqlite_summary(record, running_sessions)
            continue
        if not existing.is_running and record.session_id in running_sessions:
            existing.is_running = True

    sessions = list(sessions_by_id.values())
    sessions.sort(key=lambda s: s.last_activity, reverse=True)
    return sessions[:limit]


def _find_session_file(session_id: str) -> Path | None:
    sessions_root = _sessions_dir()
    if not sessions_root.exists():
        return None

    for session_file in sessions_root.rglob(f"*{session_id}.jsonl"):
        if session_file.is_file():
            return session_file

    for record in _sqlite_thread_records():
        if record.session_id != session_id or record.rollout_path is None:
            continue
        if record.rollout_path.is_file():
            return record.rollout_path

    # Fallback: scan for matching session_meta ID
    for session_file in sessions_root.rglob("rollout-*.jsonl"):
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                for line in f:
                    if '"type":"session_meta"' not in line:
                        continue
                    record = json.loads(line)
                    payload = record.get("payload", {})
                    if payload.get("id") == session_id:
                        return session_file
        except Exception:
            continue
    return None


def get_codex_session_detail(
    session_id: str,
    limit: int = 100,
) -> SessionDetail | None:
    session_file = _find_session_file(session_id)
    running_sessions = find_running_codex_sessions()
    if not session_file:
        for record in _sqlite_thread_records():
            if record.session_id == session_id:
                return _build_sqlite_detail(record, running_sessions)
        return None

    first_prompt: str | None = None
    last_prompt: str | None = None
    last_activity: str | None = None
    directory: str | None = None
    messages: list[SessionMessage] = []

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = record.get("timestamp")
                if timestamp:
                    last_activity = timestamp

                record_type = record.get("type")
                payload = record.get("payload", {})

                if record_type == "session_meta":
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str):
                        directory = cwd

                if record_type == "response_item" and isinstance(payload, dict):
                    if payload.get("type") != "message":
                        continue
                    role = payload.get("role")
                    if role not in ("user", "assistant"):
                        continue
                    content = payload.get("content")
                    text = _extract_text(content)
                    if role == "user" and text:
                        if not _is_environment_context(text):
                            if first_prompt is None:
                                first_prompt = text[:200]
                            last_prompt = text[:200]
                    messages.append(
                        SessionMessage(
                            role=role,
                            content=text,
                            timestamp=timestamp,
                        )
                    )

        if directory is None:
            return None

        if last_activity is None:
            mtime = session_file.stat().st_mtime
            from datetime import datetime, timezone

            last_activity = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        if limit and len(messages) > limit:
            messages = messages[-limit:]

        return SessionDetail(
            id=session_id,
            runner_type=RunnerType.CODEX,
            directory=directory,
            first_prompt=first_prompt,
            last_prompt=last_prompt,
            last_activity=last_activity,
            message_count=len(messages),
            is_running=session_id in running_sessions,
            messages=messages,
        )
    except Exception as exc:
        logger.warning(
            "Failed to parse Codex session detail",
            session_file=str(session_file),
            error=str(exc),
        )
        return None
