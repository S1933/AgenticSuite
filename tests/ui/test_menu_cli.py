"""Menu wiring (Lot 6) — parser and CLI integration tests."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from agentic_suite.cli import _build_parser, _prompt_action, main

pytestmark = pytest.mark.ui


def test_no_subcommand_routes_to_menu(tmp_path: Path, monkeypatch) -> None:
    """agentic with no args shows the menu and quits on 0."""
    monkeypatch.chdir(tmp_path)
    called: dict = {}
    monkeypatch.setattr("agentic_suite.cli.cmd_run", lambda wf_id: called.setdefault("wf", wf_id) or 0)
    monkeypatch.setattr("agentic_suite.cli._prompt_action", lambda menu: 0)
    rc = main([])
    assert rc == 0


def test_menu_workflow_action_calls_run(tmp_path: Path, monkeypatch) -> None:
    """Choosing a workflow number invokes cmd_run (which needs providers)."""
    wf_dir = tmp_path / "workflows" / "v1"
    wf_dir.mkdir(parents=True)
    (wf_dir / "bugfix.yaml").write_text(
        "id: bugfix\nversion: 1\ninitial_state: discovery\n"
        "states:\n  - id: discovery\n    terminal: false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    called: dict = {}
    monkeypatch.setattr("agentic_suite.cli.cmd_run", lambda wf_id: called.setdefault("wf", wf_id) or 0)
    # first call picks workflow 1; second call quits
    fake_inputs = iter([1, 0])
    monkeypatch.setattr(
        "agentic_suite.cli._prompt_action",
        lambda menu: next(fake_inputs),
    )
    rc = main([])
    assert rc == 0
    assert called.get("wf") == "bugfix"


def test_prompt_action_maps_inputs() -> None:
    assert _prompt_action({}, input_fn=lambda prompt: "7") == 7
    assert _prompt_action({}, input_fn=lambda prompt: "abc") is None
    assert _prompt_action({}, input_fn=lambda prompt: "") is None


def test_parser_has_menu_routing() -> None:
    parser = _build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    assert "lint" in sub.choices and "run" in sub.choices and "log" in sub.choices
    assert "menu" not in sub.choices  # menu is the no-arg default, not a subcommand


def test_no_subcommand_required() -> None:
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.command is None