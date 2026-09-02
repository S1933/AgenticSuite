"""R17 — assertion ids must not smuggle negation (ADR 0007 D3).

The regex catches patterns that negate a nominal assertion
(is_not_*, does_not_*, not_*). cannot_/fails_/failed_/invalid_ name
a condition, not the negation of another assertion (cf. ADR 0007 D5
examples — `fix_cannot_be_implemented` is the canonical formulation).
"""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


@pytest.mark.parametrize(
    "aid",
    [
        "regression_is_not_verified",
        "fix_does_not_hold",
        "x_is_not_set",
    ],
)
def test_smuggled_negation_errors(aid: str) -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["id"] = aid
    # The on_failure still points to x_is_set which is now wrong, so update
    wf["states"][0]["on_failure"][0]["when"] = aid
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R17"]
    assert len(rule_msgs) == 1, (aid, msgs)
    assert rule_msgs[0].severity == "error"


@pytest.mark.parametrize(
    "aid",
    [
        "diagnosis_is_invalidated",  # condition constatee
        "no_root_cause_found",
        "context_is_sufficient",
        "regression_is_verified",  # positive form
        "fix_cannot_be_implemented",  # condition, not negation
        "patch_is_invalid",  # condition, not negation
    ],
)
def test_positive_assertion_ids_pass(aid: str) -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["id"] = aid
    wf["states"][0]["on_failure"][0]["when"] = aid
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R17" for m in msgs), (aid, msgs)