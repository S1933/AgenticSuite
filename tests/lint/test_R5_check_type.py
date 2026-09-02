"""R5 — check.type must be in the closed set (ADR 0003 D3)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_unknown_check_type_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["checks"].append({"name": "custom", "type": "fuzzy_match"})
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R5"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"
    assert "fuzzy_match" in rule_msgs[0].message


def test_three_allowed_types_pass() -> None:
    wf = minimal_workflow()
    # context_fields_present is already there; add the two others
    wf["states"][0]["checks"].append(
        {"name": "diag_exists", "type": "artifact_exists", "id": "diagnostic"}
    )
    wf["states"][0]["checks"].append(
        {"name": "tests_pass", "type": "command_exit_zero", "command_ref": "run_tests"}
    )
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R5" for m in msgs), msgs