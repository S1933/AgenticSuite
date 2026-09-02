"""R1 — enum field references an undeclared vocabulary."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_enum_field_referencing_declared_vocabulary_passes() -> None:
    wf = minimal_workflow()
    wf["vocabularies"] = {"color": ["red", "green", "blue"]}
    cf = wf["states"][0]["context_fields"][0]
    cf["type"] = "enum"
    cf["vocabulary"] = "color"
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R1" for m in msgs), msgs


def test_enum_field_referencing_undeclared_vocabulary_errors() -> None:
    wf = minimal_workflow()
    cf = wf["states"][0]["context_fields"][0]
    cf["type"] = "enum"
    cf["vocabulary"] = "nonexistent"
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R1"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"
    assert "nonexistent" in rule_msgs[0].message