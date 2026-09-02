"""R4 — command_ref must match [a-z][a-z0-9_]* (ADR 0003 D3)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def _make_wf_with_command_ref(ref: str) -> dict:
    wf = minimal_workflow()
    wf["states"][0]["checks"].append(
        {
            "name": "tests_pass",
            "type": "command_exit_zero",
            "command_ref": ref,
        }
    )
    return wf


@pytest.mark.parametrize(
    "ref",
    ["run_tests", "test", "a", "abc_def_ghi", "x1", "x_y_z"],
)
def test_valid_command_ref_passes(ref: str) -> None:
    msgs = engine.lint(_make_wf_with_command_ref(ref))
    assert not any(m.rule_id == "R4" for m in msgs), msgs


@pytest.mark.parametrize(
    "ref",
    [
        "RunTests",  # uppercase
        "1run",  # starts with digit
        "run-tests",  # hyphen
        "run tests",  # space
        "run.tests",  # dot
        "run/tests",  # slash
    ],
)
def test_invalid_command_ref_errors(ref: str) -> None:
    msgs = engine.lint(_make_wf_with_command_ref(ref))
    rule_msgs = [m for m in msgs if m.rule_id == "R4"]
    assert len(rule_msgs) == 1, msgs
    assert rule_msgs[0].severity == "error"
    assert ref in rule_msgs[0].message