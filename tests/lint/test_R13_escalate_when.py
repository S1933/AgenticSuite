"""R13 — escalate_when items must have nature=assertion (ADR 0003 D7)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_budget_exceeded_in_escalate_when_errors() -> None:
    wf = minimal_workflow()
    wf["escalate_when"].append(
        {"id": "budget_exceeded", "nature": "check"}
    )
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R13"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_four_assertion_triggers_pass() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R13" for m in msgs)