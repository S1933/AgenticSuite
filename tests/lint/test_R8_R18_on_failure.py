"""R8/R18 — on_failure.when must reference a declared assertion id (ADR 0003 D5, ADR 0007 D4)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_on_failure_with_known_assertion_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id in {"R8", "R18"} for m in msgs)


def test_on_failure_with_unknown_assertion_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["on_failure"][0]["when"] = "ghost_assertion"
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id in {"R8", "R18"}]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"
    assert "ghost_assertion" in rule_msgs[0].message