"""R14/R15 — artifact id uniqueness and kind enum closure (ADR 0003 D8)."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_unique_artifact_ids_pass() -> None:
    msgs = engine.lint(minimal_workflow())
    assert not any(m.rule_id == "R14" for m in msgs)


def test_duplicate_artifact_id_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["produces"].append(
        {"id": "note_a", "kind": "note", "required": False}
    )
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R14"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"
    assert "duplicated" in rule_msgs[0].message


@pytest.mark.parametrize(
    "kind", ["diagnosis", "repro", "patch", "test_result", "decision", "note"]
)
def test_allowed_kinds_pass(kind: str) -> None:
    wf = minimal_workflow()
    wf["states"][0]["produces"][0]["kind"] = kind
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R15" for m in msgs)


@pytest.mark.parametrize("kind", ["memo", "log", "trace", ""])
def test_unknown_kind_errors(kind: str) -> None:
    wf = minimal_workflow()
    wf["states"][0]["produces"][0]["kind"] = kind
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R15"]
    assert len(rule_msgs) == 1, (kind, msgs)
    assert rule_msgs[0].severity == "error"