"""R21 — context.<id> evidence must be on a path to the citing state (ADR 0003 P3)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_attainable_context_evidence_passes() -> None:
    """The default fixture produces context.x in s1, cited by s1's assertions.

    Since s1 can reach itself (it produces x), the evidence is attainable.
    """
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R21" for m in msgs)


def test_undeclared_context_field_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["evidence_from"] = ["context.ghost"]
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R21"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"
    assert "ghost" in rule_msgs[0].message


def test_unreachable_context_field_errors() -> None:
    """Field y is produced in s2 but cited in s1's assertion. s1 has no path
    to s2 (s2 is terminal and s1's next is s2 — wait, s1->s2 IS a path).

    So we need a state that cannot reach itself: produce y in s2 (terminal,
    no outgoing edges) and cite it from s1. That's not unreachable; s1 -> s2.
    To make it unreachable, put the field in a state that has no path
    forward to the citing state. With current linear topology this is hard,
    so we add a branch: a state `sX` that produces y but is not on the
    forward chain from s1.
    """
    wf = minimal_workflow()
    # Add an orphan state sX that produces `orphan_field` (no path from s1)
    wf["states"].append(
        {
            "id": "sX",
            "role": "actor",
            "evaluated_by": "evaluator",
            "max_attempts": 1,
            "context_fields": [
                    {
                        "id": "orphan_field",
                        "type": "text",
                        "required": True,
                        "description": "",
                    }
                ],
            "terminal": True,
        }
    )
    wf["states"][0]["assertions"][0]["evidence_from"] = ["context.orphan_field"]
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R21"]
    assert len(rule_msgs) == 1, msgs
    assert "orphan_field" in rule_msgs[0].message