"""Command-line interface entry point for `agentic`."""

from __future__ import annotations

import argparse
import sys

from agentic_suite import __version__
from agentic_suite.lint import engine
from agentic_suite.loader import LoadError, load_workflow


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentic",
        description="Agentic Suite CLI (Lot 0: lint only)",
    )
    p.add_argument("--version", action="version", version=f"agentic {__version__}")

    sub = p.add_subparsers(dest="command", required=True)

    lint_p = sub.add_parser("lint", help="Lint a workflow YAML")
    lint_p.add_argument(
        "workflow", help="Path to the workflow YAML file"
    )
    lint_p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "lint":
        return cmd_lint(args.workflow, strict=args.strict)
    parser.error(f"unknown command: {args.command}")
    return 2  # unreachable


if __name__ == "__main__":
    raise SystemExit(main())