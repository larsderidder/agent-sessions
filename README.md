# agent-sessions

Discover and inspect local AI coding agent sessions (Claude Code, Codex, Pi).

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

## What it discovers

| Agent | Session location | Format |
|-------|-----------------|--------|
| Claude Code | `~/.claude/projects/` | JSONL per session |
| Codex | `~/.codex/sessions/` | JSONL rollout files |
| Pi | `~/.pi/agent/sessions/` | JSONL per session |

Each provider also detects whether sessions are currently running by inspecting the process table.

> Looking for a ready-made solution for supervising your agents? Check out [Tether](https://github.com/larsderidder/tether).

## Install

```bash
pip install agent-sessions
```

## License

MIT
