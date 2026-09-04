"""R10 — a locally-declared terminal reached via on_failure is a
reclassification end, reachable only from the initial state (ADR 0003 D5,
generalized — no state names hardcoded)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def _wf_with_reclass(reclass_name: str, initial: str = "s1") -> dict:
    """workflow with a local terminal *reclass_name* targeted by on_failure."""
    wf = minimal_workflow()
    wf["initial_state"] = initial
    wf["states"][0]["id"] = initial  # rename s1 -> the initial state id
    wf["states"][0]["on_failure"] = [{"to": reclass_name, "when": "failure_cond"}]
    wf["states"][0]["assertions"].append(
        {"id": "failure_cond", "description": "", "evidence_from": ["context.x"]}
    )
    wf["states"].append({"id": reclass_name, "terminal": True})
    return wf


def test_reclass_from_initial_state_passes() -> None:
    """bugfix-like: 'reclassified' targeted from the initial state is fine."""
    wf = _wf_with_reclass("reclassified", initial="discovery")
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R10" for m in msgs)


def test_descoped_from_initial_state_passes() -> None:
    """feature-like: the reclass terminal has a different name, still passes."""
    wf = _wf_with_reclass("descoped", initial="intake")
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R10" for m in msgs)


def test_reclass_from_other_state_errors() -> None:
    """Reaching a local terminal via on_failure outside the initial state."""
    wf = _wf_with_reclass("descoped", initial="intake")
    # s2 (not initial) now also routes to descoped via on_failure
    wf["states"][1]["terminal"] = False
    wf["states"][1]["on_failure"] = [{"to": "descoped", "when": "failure_cond"}]
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R10"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"
    assert "descoped" in rule_msgs[0].message


def test_done_terminal_via_next_not_flagged() -> None:
    """A terminal that is only a next: target is not a reclassification end."""
    wf = minimal_workflow()
    wf["initial_state"] = "s1"
    msgs = engine.lint(wf)  # s2 is terminal, reached via next
    assert not any(m.rule_id == "R10" for m in msgs)


def test_escape_state_terminal_not_flagged() -> None:
    """abandoned (escape_state terminal) routed via on_failure is exempt."""
    wf = minimal_workflow()
    wf["initial_state"] = "s1"
    wf["states"][1]["on_failure"] = [{"to": "abandoned", "when": "nominal_cond"}]
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R10" for m in msgs)


def test_missing_initial_state_skips_r10() -> None:
    """Without initial_state R20 screams; R10 stays out of the way."""
    wf = _wf_with_reclass("descoped")
    wf.pop("initial_state")
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R10" for m in msgs)