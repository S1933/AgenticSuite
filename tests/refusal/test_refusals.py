"""Refusal tests — schema-level refusals the lint must enforce."""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.refusal


def test_F1_command_ref_malformed_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["checks"].append(
        {"name": "x", "type": "command_exit_zero", "command_ref": "RunTests"}
    )
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F2_unknown_check_type_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["checks"].append({"name": "x", "type": "magic_eye"})
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F3_unknown_assertion_in_on_failure_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["on_failure"][0]["when"] = "nonexistent"
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F4_reclassified_from_wrong_state_refused() -> None:
    wf = minimal_workflow()
    wf["states"][1]["terminal"] = False
    wf["states"][1]["on_failure"] = [{"to": "reclassified", "when": "x_is_set"}]
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F5_duplicate_artifact_id_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["produces"].append(
        {"id": "note_a", "kind": "note", "required": False}
    )
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F6_negative_assertion_id_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["id"] = "x_is_not_set"
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F8_undeclared_vocabulary_refused() -> None:
    wf = minimal_workflow()
    cf = wf["states"][0]["context_fields"][0]
    cf["type"] = "enum"
    cf["vocabulary"] = "ghost"
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F_no_initial_state_refused() -> None:
    wf = minimal_workflow()
    wf.pop("initial_state")
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F_evidence_from_empty_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["evidence_from"] = []
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)


def test_F_unattainable_context_evidence_refused() -> None:
    wf = minimal_workflow()
    wf["states"][0]["assertions"][0]["evidence_from"] = ["context.ghost_field"]
    msgs = engine.lint(wf)
    assert engine.has_errors(msgs)