# agent-sessions

[![PyPI](https://img.shields.io/pypi/v/agent-sessions)](https://pypi.org/project/agent-sessions/)
[![Tests](https://github.com/larsderidder/agent-sessions/actions/workflows/test.yml/badge.svg)](https://github.com/larsderidder/agent-sessions/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/pypi/pyversions/agent-sessions)](https://pypi.org/project/agent-sessions/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Discover and inspect local AI coding agent sessions (Claude Code, Codex, OpenCode, Pi).

> **Looking for a ready-made supervision tool?** Check out [Tether](https://github.com/larsderidder/tether).

## Install

```bash
pip install agent-sessions
```

## Usage

```python
from agent_sessions import discover_sessions, get_session_detail, RunnerType

# Find all recent sessions
sessions = discover_sessions()
for s in sessions:
    print(f"{s.runner_type.value}: {s.directory} ({s.message_count} messages)")

# Filter by agent type
claude_sessions = discover_sessions(runner_type=RunnerType.CLAUDE_CODE)

# Filter by project directory
project_sessions = discover_sessions(directory="/home/user/my-project")

# Load full message history
detail = get_session_detail(sessions[0].id, sessions[0].runner_type)
for msg in detail.messages:
    print(f"[{msg.role}] {msg.content[:80]}")
```

CLI:

```bash
agent-sessions list --runner-type codex
agent-sessions show <session-id> --runner-type codex --json
```

Release-candidate packaging:

```bash
python scripts/build_rc_assets.py \
  --dist-dir dist \
  --output-dir dist-rc \
  --package-name agent-sessions-rc \
  --project-name agent-sessions \
  --display-name "agent-sessions" \
  --homepage https://github.com/larsderidder/agent-sessions \
  --release-tag v0.2.1-rc1 \
  --repo-owner Adminrealagi \
  --repo-name agent-sessions \
  --primary-command agent-sessions=agent-sessions-rc
```

## Supported agents

| Agent | Session location | Format |
|-------|-----------------|--------|
| Claude Code | `~/.claude/projects/` | JSONL per session |
| Codex | `~/.codex/sessions/` plus `~/.codex/state_*.sqlite` | JSONL rollout files plus SQLite thread metadata |
| OpenCode | `~/.local/share/opencode/opencode.db` | SQLite database |
| Pi | `~/.pi/agent/sessions/` | JSONL per session |

Each provider also detects whether sessions are currently running by inspecting the process table.

For Codex, discovery falls back to the SQLite `threads` table when a session has
been created in `state_*.sqlite` but the rollout file has not been flushed yet.

## Configuration

All providers support environment variables to override default paths:

| Variable | Provider | Default |
|----------|----------|---------|
| `CLAUDE_HOME` | Claude Code | `~/.claude` |
| `CODEX_HOME` | Codex | `~/.codex` |
| `XDG_DATA_HOME` | OpenCode | `~/.local/share` |
| `PI_SESSIONS_DIR` | Pi | `~/.pi/agent/sessions` |

OpenCode uses a centralized database at `$XDG_DATA_HOME/opencode/opencode.db` (defaults to `~/.local/share/opencode/opencode.db`).

## Status

Beta. The API may change between minor versions until 1.0.

## License

MIT
