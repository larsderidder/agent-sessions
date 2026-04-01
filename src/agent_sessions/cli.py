"""CLI entry point for agent-sessions."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable

from agent_sessions import discover_sessions, get_session_detail
from agent_sessions.models import RunnerType, SessionDetail, SessionSummary


def _runner_type(value: str) -> RunnerType:
    try:
        return RunnerType(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid runner type: {value}"
        ) from exc


def _summary_to_dict(summary: SessionSummary) -> dict[str, object]:
    return summary.model_dump()


def _detail_to_dict(detail: SessionDetail) -> dict[str, object]:
    return detail.model_dump()


def _print_summary_table(sessions: Iterable[SessionSummary]) -> None:
    print("ID           TYPE         RUNNING  MESSAGES  DIRECTORY")
    print("------------ ------------ -------- --------- ---------")
    for session in sessions:
        running = "yes" if session.is_running else "no"
        print(
            f"{session.id[:12]:12} {session.runner_type.value:12} "
            f"{running:8} {session.message_count:9} {session.directory}"
        )


def _print_detail(detail: SessionDetail) -> None:
    print(f"ID: {detail.id}")
    print(f"Type: {detail.runner_type.value}")
    print(f"Directory: {detail.directory}")
    print(f"Running: {'yes' if detail.is_running else 'no'}")
    print(f"Messages: {detail.message_count}")
    for message in detail.messages:
        print()
        print(f"[{message.role}] {message.content}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-sessions",
        description="Discover and inspect local AI coding agent sessions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List discovered sessions")
    list_parser.add_argument("--directory", help="Filter by directory")
    list_parser.add_argument(
        "--runner-type",
        type=_runner_type,
        help="Filter by runner type",
    )
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum sessions")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON")

    show_parser = sub.add_parser("show", help="Show one session in detail")
    show_parser.add_argument("session_id", help="Session id")
    show_parser.add_argument(
        "--runner-type",
        type=_runner_type,
        required=True,
        help="Runner type for the session",
    )
    show_parser.add_argument("--limit", type=int, default=100, help="Maximum messages")
    show_parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        sessions = discover_sessions(
            directory=args.directory,
            runner_type=args.runner_type,
            limit=args.limit,
        )
        if args.json:
            json.dump([_summary_to_dict(session) for session in sessions], sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        if not sessions:
            print("No sessions found.")
            return 0
        _print_summary_table(sessions)
        return 0

    if args.command == "show":
        detail = get_session_detail(
            session_id=args.session_id,
            runner_type=args.runner_type,
            limit=args.limit,
        )
        if detail is None:
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        if args.json:
            json.dump(_detail_to_dict(detail), sys.stdout, indent=2)
            sys.stdout.write("\n")
            return 0
        _print_detail(detail)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
