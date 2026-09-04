"""R22 — skills must be declared per state (ADR 0006 D1).

Format per entry: {id: snake_case, use_when: free prose (optional)}.
A state's skills list is the closed set of invocable skills from that
state; no workflow-level or config-level declaration exists.
"""

from __future__ import annotations

import pytest

from agentic_suite.lint import engine
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.lint_rule


def test_valid_skills_passes() -> None:
    wf = minimal_workflow()
    wf["states"][0]["skills"] = [
        {"id": "code_review", "use_when": "A patch exists to review"},
        {"id": "test_audit"},
    ]
    msgs = engine.lint(wf)
    assert not any(m.rule_id == "R22" for m in msgs), msgs


def test_skill_id_must_be_snake_case() -> None:
    wf = minimal_workflow()
    wf["states"][0]["skills"] = [{"id": "CodeReview"}]
    msgs = engine.lint(wf)
    rule_msgs = [m for m in msgs if m.rule_id == "R22"]
    assert len(rule_msgs) == 1
    assert rule_msgs[0].severity == "error"


def test_skill_entry_must_be_mapping() -> None:
    wf = minimal_workflow()
    wf["states"][0]["skills"] = ["code_review"]  # string, not mapping
    msgs = engine.lint(wf)
    assert any(m.rule_id == "R22" and m.severity == "error" for m in msgs)


def test_skill_entry_missing_id_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["skills"] = [{"use_when": "whatever"}]
    msgs = engine.lint(wf)
    assert any(m.rule_id == "R22" and m.severity == "error" for m in msgs)


def test_skill_use_when_must_be_prose_string() -> None:
    wf = minimal_workflow()
    wf["states"][0]["skills"] = [{"id": "code_review", "use_when": ["x"]}]
    msgs = engine.lint(wf)
    assert any(m.rule_id == "R22" and m.severity == "error" for m in msgs)


def test_duplicate_skill_ids_errors() -> None:
    wf = minimal_workflow()
    wf["states"][0]["skills"] = [{"id": "code_review"}, {"id": "code_review"}]
    msgs = engine.lint(wf)
    assert any(m.rule_id == "R22" and m.severity == "error" for m in msgs)