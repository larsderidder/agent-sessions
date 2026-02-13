"""Utilities for detecting running agent sessions via process inspection."""

from __future__ import annotations

import re
import subprocess


def find_running_claude_sessions() -> set[str]:
    """Return set of Claude Code session IDs that are currently running.

    Detection method: Parse ``ps`` output for ``claude --resume <id>`` processes.
    """
    running: set[str] = set()
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return running

        for line in result.stdout.splitlines():
            if "claude" not in line:
                continue
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "--resume" and i + 1 < len(parts):
                    sid = parts[i + 1]
                    if len(sid) >= 32 and "-" in sid:
                        running.add(sid)
                    break
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return running


def find_running_codex_sessions() -> set[str]:
    """Return set of Codex CLI session IDs that are currently running.

    Detection method: Parse ``ps`` output for ``codex resume`` processes.
    """
    running: set[str] = set()
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return running

        for line in result.stdout.splitlines():
            if "codex resume" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "resume" and i + 1 < len(parts):
                        session_id = parts[i + 1]
                        if len(session_id) >= 32 and "-" in session_id:
                            running.add(session_id)
                        break
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return running


def find_running_pi_sessions() -> set[str]:
    """Return set of Pi session IDs that are currently running.

    Detection method: Parse ``ps`` output for ``pi`` processes and extract
    UUID-shaped session identifiers.
    """
    running: set[str] = set()
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return running

        for line in result.stdout.splitlines():
            if "pi-coding-agent" not in line and "/pi " not in line:
                continue
            uuid_match = re.search(
                r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
                line,
            )
            if uuid_match:
                running.add(uuid_match.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return running


def is_claude_session_running(session_id: str) -> bool:
    """Check if a specific Claude Code session is running."""
    return session_id in find_running_claude_sessions()


def is_codex_session_running(session_id: str) -> bool:
    """Check if a specific Codex session is running."""
    return session_id in find_running_codex_sessions()


def is_pi_session_running(session_id: str) -> bool:
    """Check if a specific Pi session is running."""
    return session_id in find_running_pi_sessions()
