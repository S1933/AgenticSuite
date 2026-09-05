"""Menu UI (Lot 6) — workflows + sessions listing and numbered actions.

The menu must be usable without memorising the CLI: `agentic` with no
subcommand shows what exists (workflows, sessions), and every action is
numbered. Rendering is pure and tested; only the input loop touches stdin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_suite.session import append_block, new_session
from agentic_suite.ui import action_from_menu, build_menu, render_menu

pytestmark = pytest.mark.ui


def _repo(tmp_path: Path) -> Path:
    """A minimal project root: one workflow, one real chained session."""
    vdir = tmp_path / "workflows" / "v1"
    vdir.mkdir(parents=True)
    (vdir / "bugfix.yaml").write_text(
        "id: bugfix\nversion: 1\ninitial_state: discovery\n"
        "states:\n  - id: discovery\n    terminal: false\n",
        encoding="utf-8",
    )
    sdir = tmp_path / "sessions" / "bugfix-abc123"
    sdir.mkdir(parents=True)
    jp = sdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    append_block(jp, {
        "seq": 1, "timestamp": "t", "type": "transition",
        "from_state": "discovery", "to_state": "blocked",
        "criteria_verdicts": {}, "workflow_version": 1,
    })
    (sdir / "context.json").write_text("{}", encoding="utf-8")
    return tmp_path


def test_build_menu_lists_workflows_and_sessions(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    menu = build_menu(root)
    assert [w["id"] for w in menu["workflows"]] == ["bugfix"]
    assert [s["id"] for s in menu["sessions"]] == ["bugfix-abc123"]


def test_session_entry_carries_current_state_and_integrity(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    menu = build_menu(root)
    session = menu["sessions"][0]
    assert session["state"] == "blocked"
    assert session["integrity"] == "ok"


def test_render_menu_shows_workflow_and_session_lines(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    text = render_menu(build_menu(root))
    assert "workflows" in text and "bugfix" in text
    assert "bugfix-abc123" in text and "blocked" in text


def test_corrupted_session_flagged_not_crashing(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    jp = root / "sessions" / "bugfix-abc123" / "session.jsonl"
    # truncate INSIDE the last line -> partial JSON block (hardware-style)
    data = jp.read_text(encoding="utf-8")
    jp.write_text(data[: len(data) // 2], encoding="utf-8")
    menu = build_menu(root)
    assert menu["sessions"][0]["integrity"] == "invalid"


def test_action_from_menu_maps_number_to_workflow_or_session(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    menu = build_menu(root)
    # workflows first, then sessions
    assert action_from_menu(menu, 1) == {"kind": "workflow", "id": "bugfix"}
    assert action_from_menu(menu, 2) == {"kind": "session", "id": "bugfix-abc123"}
    assert action_from_menu(menu, 0) is None
    assert action_from_menu(menu, 3) is None