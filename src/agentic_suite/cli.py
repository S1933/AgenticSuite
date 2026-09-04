"""Command-line interface entry point for `agentic`."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
import uuid
from pathlib import Path

from agentic_suite import __version__
from agentic_suite.lint import engine
from agentic_suite.loader import LoadError, load_workflow
from agentic_suite.runner import run_attempt
from agentic_suite.session import (
    SessionIntegrityViolation,
    append_block,
    load_journal,
    new_session,
)

SESSIONS_DIR = "sessions"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentic",
        description="Agentic Suite CLI (Lot 4: session lifecycle)",
    )
    p.add_argument("--version", action="version", version=f"agentic {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    lint_p = sub.add_parser("lint", help="Lint a workflow YAML")
    lint_p.add_argument("workflow", help="Path to the workflow YAML file")
    lint_p.add_argument(
        "--strict", action="store_true", help="Treat warnings as errors"
    )

    start_p = sub.add_parser("start", help="Open and run a session")
    start_p.add_argument("workflow", help="Workflow id (looked up in workflows/v<N>/)")

    status_p = sub.add_parser("status", help="Show session state and integrity")
    status_p.add_argument("session", help="Session id")

    resume_p = sub.add_parser("resume", help="Resume a session from blocked")
    resume_p.add_argument("session", help="Session id")
    resume_p.add_argument("to_state", help="State to resume into")

    log_p = sub.add_parser("log", help="Show the session journal")
    log_p.add_argument("session", help="Session id")

    return p


def cmd_lint(workflow_path: str, strict: bool = False) -> int:
    """Run lint and return a Unix-style exit code (0 ok, 1 errors)."""
    try:
        wf = load_workflow(workflow_path)
    except LoadError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    messages = engine.lint(wf)
    has_error = engine.has_errors(messages)
    has_warning = any(m.severity == "warning" for m in messages)

    for m in messages:
        print(m)
    if not messages:
        print(f"ok: {workflow_path} passes lint with 0 errors and 0 warnings")
        return 0
    if has_error:
        return 1
    if strict and has_warning:
        return 1
    return 0


def _resolve_workflow_path(workflow_id: str) -> Path:
    """Resolve workflows/v<N>/<id>.yaml from the project root (cwd)."""
    root = Path.cwd()
    vdir = root / "workflows"
    if not vdir.is_dir():
        raise FileNotFoundError(f"no workflows/ directory under {root}")
    for version_dir in sorted(vdir.iterdir(), reverse=True):
        if version_dir.is_dir() and version_dir.name.startswith("v"):
            candidate = version_dir / f"{workflow_id}.yaml"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"workflow '{workflow_id}' not found under {vdir}")


def _evaluator_cmd_from_env() -> list[str]:
    raw = os.environ.get("AGENTIC_EVALUATOR_CMD")
    if not raw:
        raise RuntimeError(
            "AGENTIC_EVALUATOR_CMD is not set — no evaluator provider wired yet "
            "(real provider wiring lands with the provider adapters)."
        )
    return shlex.split(raw)


def _session_dir(session_id: str) -> Path:
    return Path.cwd() / SESSIONS_DIR / session_id


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def cmd_start(workflow_id: str) -> int:
    """Open a session and run one attempt of the initial state (Lot 4c)."""
    try:
        workflow_path = _resolve_workflow_path(workflow_id)
        wf = load_workflow(workflow_path)
    except (LoadError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    session_id = f"{workflow_id}-{uuid.uuid4().hex[:8]}"
    sdir = _session_dir(session_id)
    sdir.mkdir(parents=True, exist_ok=True)
    jp = sdir / "session.jsonl"

    initial = wf.get("initial_state")
    if not initial:
        print("error: workflow has no initial_state", file=sys.stderr)
        return 2

    new_session(jp, to_state=initial, workflow_version=wf.get("version", 1))
    # empty context file: discovery fills it (ADR 0001)
    (sdir / "context.json").write_text("{}", encoding="utf-8")

    try:
        evaluator_cmd = _evaluator_cmd_from_env()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        result = run_attempt(
            session_path=jp,
            session_dir=sdir,
            workflow=wf,
            evaluator_cmd=evaluator_cmd,
            evaluator_env=dict(os.environ),
            project_root=Path.cwd(),
            machine_home=None,
        )
    except SessionIntegrityViolation as e:
        print(f"error: session integrity violation: {e}", file=sys.stderr)
        return 3

    t = result.transition
    print(f"session {session_id}")
    print(f"transition: {t.kind} -> {t.to or '(terminal)'}"
          + (f" ({t.reason})" if t.reason else ""))
    return 0


def cmd_status(session_id: str) -> int:
    """Show current state and journal integrity (ADR 0004 D4)."""
    jp = _session_dir(session_id) / "session.jsonl"
    if not jp.is_file():
        print(f"error: no session '{session_id}'", file=sys.stderr)
        return 2
    try:
        journal = load_journal(jp)
    except SessionIntegrityViolation as e:
        print(f"error: session integrity violation: {e}", file=sys.stderr)
        return 3
    current = journal[-1].get("to_state")
    print(f"session {session_id}")
    print(f"state: {current}")
    print(f"transitions: {len(journal)} blocks")
    print("integrity: ok")
    return 0


def cmd_resume(session_id: str, to_state: str) -> int:
    """Resume from blocked via session_resumed (ADR 0004 D8)."""
    sdir = _session_dir(session_id)
    jp = sdir / "session.jsonl"
    if not jp.is_file():
        print(f"error: no session '{session_id}'", file=sys.stderr)
        return 2
    try:
        load_journal(jp)  # verify before resume
    except SessionIntegrityViolation as e:
        print(f"error: session integrity violation: {e}", file=sys.stderr)
        return 3
    append_block(jp, {
        "seq": _next_seq(jp),
        "timestamp": _now_iso(),
        "type": "session_resumed",
        "from_state": "blocked",
        "to_state": to_state,
        "resumed_at": _now_iso(),
        "resumed_by": "human",
    })
    print(f"session {session_id}: resumed -> {to_state}")
    return 0


def _next_seq(jp: Path) -> int:
    journal = load_journal(jp)
    return journal[-1]["seq"] + 1


def cmd_log(session_id: str) -> int:
    """Show the journal with per-block detail and invalid markers (D5)."""
    jp = _session_dir(session_id) / "session.jsonl"
    if not jp.is_file():
        print(f"error: no session '{session_id}'", file=sys.stderr)
        return 2
    try:
        journal = load_journal(jp)
    except SessionIntegrityViolation as e:
        print(f"error: session integrity violation: {e}", file=sys.stderr)
        return 3
    for block in journal:
        marker = " [INVALID]" if block.get("_invalid") else ""
        detail = (
            f"{block.get('type')} {block.get('from_state')} -> "
            f"{block.get('to_state')} (seq {block.get('seq')}){marker}"
        )
        print(detail)
        for key in ("criteria_evaluated", "evidence"):
            if block.get(key):
                print(f"    {key}: {json.dumps(block[key], ensure_ascii=False)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "lint":
        return cmd_lint(args.workflow, strict=args.strict)
    if args.command == "start":
        return cmd_start(args.workflow)
    if args.command == "status":
        return cmd_status(args.session)
    if args.command == "resume":
        return cmd_resume(args.session, args.to_state)
    if args.command == "log":
        return cmd_log(args.session)
    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())