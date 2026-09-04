"""skill_invoked journal event — ADR 0006 D4/D5.

A skill invocation is a typed session block carrying skill_id, state_id,
role, and ≤200-char input/output summaries (D4). It participates in the
chain like any other block. UNDECLARED skill invocations are recorded but
flagged for a post-execution warning (D5): the runtime does not refuse,
it signals the deviation.
"""

from __future__ import annotations

import json

import pytest

from agentic_suite.session import (
    SessionIntegrityViolation,
    append_block,
    load_journal,
    new_session,
)
from agentic_suite.skills import record_skill_invocation, undeclared_skill_ids

pytestmark = pytest.mark.session


def _base_invocation(**overrides: str) -> dict:
    block = {
        "seq": 1,
        "timestamp": "2026-09-02T21:00:00Z",
        "type": "skill_invoked",
        "skill_id": "code_review",
        "state_id": "fix",
        "role": "actor",
        "input_summary": "review the patch",
        "output_summary": "two findings",
    }
    block.update(overrides)
    return block


def test_skill_invoked_block_chains_and_loads(tmp_path_factory) -> None:
    """D4: skill_invoked is a normal journal block, covered by the chain."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    append_block(jp, _base_invocation())
    journal = load_journal(jp)
    assert journal[1]["type"] == "skill_invoked"
    assert journal[1]["skill_id"] == "code_review"
    assert journal[1]["seq"] == 1


def test_skill_invoked_integrity_is_enforced(tmp_path_factory) -> None:
    """Tampering with a skill_invoked block breaks the chain like any other."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    append_block(jp, _base_invocation())
    lines = jp.read_text().splitlines()
    edited = json.loads(lines[1])
    edited["skill_id"] = "evil_skill"
    lines[1] = json.dumps(edited)
    jp.write_text("\n".join(lines))
    with pytest.raises(SessionIntegrityViolation):
        load_journal(jp)


def test_record_skill_invocation_appends(tmp_path_factory) -> None:
    """D4: the runtime helper appends a validated skill_invoked block."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="fix", workflow_version=1)
    record_skill_invocation(
        jp,
        skill_id="code_review",
        state_id="fix",
        role="actor",
        input_summary="the patch",
        output_summary="ok",
    )
    journal = load_journal(jp)
    assert journal[1]["type"] == "skill_invoked"
    assert journal[1]["skill_id"] == "code_review"
    assert journal[1]["state_id"] == "fix"
    assert len(journal[1]["input_summary"]) <= 200
    assert len(journal[1]["output_summary"]) <= 200


def test_summary_over_200_chars_rejected() -> None:
    """D4: summaries are capped at 200 chars."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        jp = Path(td) / "session.jsonl"
        new_session(jp, to_state="fix", workflow_version=1)
        with pytest.raises(ValueError):
            record_skill_invocation(
                jp, skill_id="s", state_id="fix", role="actor",
                input_summary="x" * 201, output_summary="ok",
            )


def test_undeclared_skill_ids_detected_for_warning() -> None:
    """D5: invocations not in the state's declared skills get flagged."""
    journal = [
        {"type": "session_opened"},
        {"type": "skill_invoked", "state_id": "fix",
         "skill_id": "undeclared_skill"},
    ]
    declared = {"code_review", "test_audit"}
    flagged = undeclared_skill_ids(journal, declared)
    assert flagged == ["undeclared_skill"]


def test_declared_skill_not_flagged() -> None:
    journal = [
        {"type": "skill_invoked", "state_id": "fix", "skill_id": "code_review"},
    ]
    assert undeclared_skill_ids(journal, {"code_review"}) == []