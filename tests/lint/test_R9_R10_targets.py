"""R9/R10 — on_failure.to must target a declared state or escape_state; reclassified only from discovery."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_on_failure_to_escape_state_passes() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R9" for m in msgs)


def test_on_failure_to_unknown_target_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["on_failure"][0]["to"] = "nowhere"
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R9"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_reclassified_only_from_discovery_passes() -> None:
    wf = minimal_workflow()
    wf["states"][0]["id"] = "discovery"
    wf["states"][0]["on_failure"][0]["to"] = "reclassified"
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R10" for m in msgs)


def test_reclassified_from_other_state_errors() -> None:
    wf = minimal_workflow()
    wf["states"][1]["terminal"] = False
    wf["states"][1]["on_failure"] = [{"to": "reclassified", "when": "x_is_set"}]
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R10"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"