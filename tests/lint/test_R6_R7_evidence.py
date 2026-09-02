"""R6/R7 — assertion must have non-empty evidence_from (ADR 0003 D4)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_assertion_without_evidence_from_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0].pop("evidence_from")
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R6"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_assertion_with_empty_evidence_from_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["evidence_from"] = []
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R7"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_assertion_with_evidence_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id in {"R6", "R7"} for m in msgs)