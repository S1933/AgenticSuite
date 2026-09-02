"""R16 — non-terminal states must declare evaluated_by (ADR 0003 D9 + P1)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_evaluator_evaluated_by_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R16" for m in msgs)


def test_missing_evaluated_by_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0].pop("evaluated_by")
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R16"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_invalid_role_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["evaluated_by"] = "reviewer"
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R16"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_terminal_state_without_evaluated_by_passes() -> None:
    wf = minimal_workflow()
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R16" for m in msgs)