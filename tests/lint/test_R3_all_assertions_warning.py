"""R3 — state with no checks triggers a lint warning (ADR 0003 D2)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_state_with_only_assertions_warns() -> None:
    wf = minimal_workflow()
    wf["states"][0]["checks"] = []
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R3"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "warning"


def test_state_with_checks_does_not_warn() -> None:
    wf = minimal_workflow()
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R3" for m in msgs)