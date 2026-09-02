"""R11/R12 — budget values must be positive integers."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


@pytest.mark.parametrize("bad", [0, -1, "2", 1.5])
def test_bad_max_attempts_errors(bad: object) -> None:
    wf = minimal_workflow()
    wf["states"][0]["max_attempts"] = bad
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R11"]
    assert len(rule_msgs) == 1, (bad, msgs)
    assert rule_msgs[0].severity == "error"


def test_valid_max_attempts_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R11" for m in msgs)


@pytest.mark.parametrize("bad", [0, -5, "20", 2.0])
def test_bad_max_transitions_errors(bad: object) -> None:
    wf = minimal_workflow()
    wf["max_transitions"] = bad
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R12"]
    assert len(rule_msgs) == 1, (bad, msgs)
    assert rule_msgs[0].severity == "error"


def test_valid_max_transitions_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R12" for m in msgs)