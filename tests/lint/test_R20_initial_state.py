"""R20 — workflow must declare initial_state (ADR 0003 P2)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_initial_state_present_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R20" for m in msgs)


def test_missing_initial_state_errors() -> None:
    wf = minimal_workflow()
    wf.pop("initial_state")
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R20"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_initial_state_must_be_declared_state() -> None:
    wf = minimal_workflow()
    wf["initial_state"] = "ghost_state"
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R20"]
    assert len(rule_msgs) == 1
    assert "ghost_state" in rule_msgs[0].message


def test_initial_state_cannot_be_escape_state() -> None:
    wf = minimal_workflow()
    wf["initial_state"] = "blocked"
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R20"]
    assert len(rule_msgs) == 1
    assert "escape_state" in rule_msgs[0].message