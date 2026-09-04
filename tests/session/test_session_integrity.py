"""Session journal integrity — ADR 0004 D3/D4/D5.

Covers the ADR 0004 validation criteria:
  5. canonical serialization produces an identical hash after two writes
  1. hand-edited session (state modified) -> blocked, session_integrity_violation
  2. truncated journal -> blocked, same reason
  6. corruption in the middle invalidates every later block, no silent error
  3. overwritten artifact invalidates later transitions that cited it
"""

from __future__ import annotations

import json

import pytest

from agentic_suite.session import (
    SessionIntegrityViolation,
    append_block,
    block_hash,
    canonical_bytes,
    count_budget_transitions,
    load_journal,
    new_session,
)

pytestmark = pytest.mark.session


def _opened_block() -> dict:
    return {
        "seq": 0,
        "timestamp": "2026-09-02T20:00:00Z",
        "type": "session_opened",
        "from_state": None,
        "to_state": "discovery",
        "attempt_counter": {"discovery": 1},
        "workflow_version": 1,
    }


def test_canonical_serialization_is_stable() -> None:
    """ADR 0004 validation #5: two writes of the same block hash identically."""
    block = _opened_block()
    assert canonical_bytes(block) == canonical_bytes(dict(block))
    # key order must not matter
    reordered = {k: block[k] for k in reversed(list(block))}
    assert canonical_bytes(reordered) == canonical_bytes(block)


def test_canonical_serialization_is_minimal() -> None:
    """No whitespace, sorted keys, compact separators."""
    raw = canonical_bytes({"b": 1, "a": [2, 3]})
    assert raw == b'{"a":[2,3],"b":1}'


def test_hash_excludes_prev_hash_and_hash_fields() -> None:
    """D3: hash is computed on the canonical block BEFORE prev_hash/hash are inserted."""
    block = _opened_block()
    h1 = block_hash(block)
    # a block that already carries hash fields must hash identically (fields ignored)
    forged = dict(block)
    forged["hash"] = "x" * 64
    forged["prev_hash"] = "y" * 64
    assert block_hash(forged) == h1


def test_new_session_writes_opened_block_with_zero_prev_hash(tmp_path_factory) -> None:
    """D3: initial block has prev_hash = 64 zeros."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    lines = jp.read_text().splitlines()
    assert len(lines) == 1
    first = json.loads(lines[0])
    assert first["seq"] == 0
    assert first["type"] == "session_opened"
    assert first["prev_hash"] == "0" * 64
    assert len(first["hash"]) == 64


def test_append_links_previous_hash(tmp_path_factory) -> None:
    """D2/D3: each block carries prev_hash of the previous block."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    append_block(jp, {"seq": 1, "timestamp": "2026-09-02T20:01:00Z",
                      "type": "transition", "from_state": "discovery",
                      "to_state": "investigation",
                      "criteria_evaluated": [], "evidence": [],
                      "evaluator": "evaluator",
                      "attempt_counter": {"investigation": 1},
                      "workflow_version": 1})
    b0, b1 = (json.loads(l) for l in jp.read_text().splitlines())
    assert b1["prev_hash"] == b0["hash"]
    # chain recomputed from scratch matches
    chain = load_journal(jp)
    assert [b["seq"] for b in chain] == [0, 1]


def test_hand_edited_state_raises_integrity_violation(tmp_path_factory) -> None:
    """ADR 0004 validation #1: state edited by hand -> blocked."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    # simulate a rogue agent rewriting the target state
    raw = jp.read_text()
    lines = raw.splitlines()
    edited = json.loads(lines[0])
    edited["to_state"] = "done"
    lines[0] = json.dumps(edited)
    jp.write_text("\n".join(lines))
    with pytest.raises(SessionIntegrityViolation):
        load_journal(jp)


def test_truncated_journal_raises_integrity_violation(tmp_path_factory) -> None:
    """ADR 0004 validation #2: truncated journal -> blocked.

    A block removed from the middle leaves a seq gap; a half-written
    final line is a hardware-level truncation. Both must be refused.
    """
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    for i in (1, 2):
        append_block(jp, {"seq": i, "timestamp": f"2026-09-02T20:0{i}:00Z",
                          "type": "transition", "from_state": "s",
                          "to_state": f"s{i}",
                          "criteria_evaluated": [], "evidence": [],
                          "evaluator": "evaluator",
                          "attempt_counter": {f"s{i}": 1},
                          "workflow_version": 1})

    # Case A: middle block removed -> seq gap (0, 2)
    lines = jp.read_text().splitlines()
    jp.write_text("\n".join(lines[:1] + lines[2:]))
    with pytest.raises(SessionIntegrityViolation):
        load_journal(jp)

    # Case B: hardware truncation -> final line is partial JSON
    jp.write_text("\n".join(lines) + "\n")
    with open(jp, "a", encoding="utf-8") as f:
        f.write('{"seq": 3, "timestamp": "2026')
    with pytest.raises(SessionIntegrityViolation):
        load_journal(jp)


def test_middle_corruption_invalidates_all_later_blocks(tmp_path_factory) -> None:
    """ADR 0004 validation #6: corruption in the middle -> every later block fails."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    for i in range(1, 4):
        append_block(jp, {"seq": i, "timestamp": f"2026-09-02T20:0{i}:00Z",
                          "type": "transition", "from_state": "s",
                          "to_state": f"s{i}",
                          "criteria_evaluated": [], "evidence": [],
                          "evaluator": "evaluator",
                          "attempt_counter": {f"s{i}": 1},
                          "workflow_version": 1})
    lines = jp.read_text().splitlines()
    mid = json.loads(lines[1])
    mid["to_state"] = "tampered"
    lines[1] = json.dumps(mid)
    jp.write_text("\n".join(lines))
    with pytest.raises(SessionIntegrityViolation):
        load_journal(jp)


def test_artifact_overwrite_invalidates_later_citing_transitions(tmp_path_factory) -> None:
    """ADR 0004 D5 + validation #3: overwritten artifact invalidates citing transitions."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    # transition 1 cites artifact 'diagnosis'
    append_block(jp, {"seq": 1, "timestamp": "2026-09-02T20:01:00Z",
                      "type": "artifact_produced", "from_state": "investigation",
                      "to_state": "investigation", "artifact_id": "diagnosis",
                      "artifact_path": "artifacts/diagnosis.json",
                      "artifact_hash": "h-v1", "artifact_kind": "diagnosis",
                      "attempt_counter": {"investigation": 1},
                      "workflow_version": 1})
    # transition 2 cites the artifact in its evidence
    append_block(jp, {"seq": 2, "timestamp": "2026-09-02T20:02:00Z",
                      "type": "transition", "from_state": "investigation",
                      "to_state": "fix", "criteria_evaluated": ["diag_ok"],
                      "evidence": ["artifacts.diagnosis"],
                      "evaluator": "evaluator",
                      "attempt_counter": {"fix": 1},
                      "workflow_version": 1})
    # artifact overwritten later
    append_block(jp, {"seq": 3, "timestamp": "2026-09-02T20:03:00Z",
                      "type": "artifact_overwritten", "from_state": "validation",
                      "to_state": "investigation", "artifact_id": "diagnosis",
                      "artifact_path": "artifacts/diagnosis.json",
                      "artifact_hash": "h-v2", "artifact_kind": "diagnosis",
                      "attempt_counter": {"investigation": 2},
                      "workflow_version": 1})
    journal = load_journal(jp)
    # transition 2 (which cited the old artifact) must be marked invalid
    tr2 = journal[2]
    assert tr2["type"] == "transition"
    assert tr2["_invalid"] is True
    # the overwrite block itself and the opened block stay valid
    assert not journal[0].get("_invalid")
    assert not journal[3].get("_invalid")


def test_hash_is_sha256_hex_64() -> None:
    h = block_hash(_opened_block())
    assert len(h) == 64
    int(h, 16)  # hex


def test_session_resumed_does_not_consume_budget(tmp_path_factory) -> None:
    """ADR 0004 D8 + validation #4: resume from blocked is not a budget transition."""
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    append_block(jp, {"seq": 1, "timestamp": "2026-09-02T20:01:00Z",
                      "type": "transition", "from_state": "discovery",
                      "to_state": "blocked",
                      "criteria_evaluated": [], "evidence": [],
                      "evaluator": "evaluator",
                      "attempt_counter": {"blocked": 1},
                      "workflow_version": 1})
    # human resume: typed separately, must not count against max_transitions
    append_block(jp, {"seq": 2, "timestamp": "2026-09-02T20:02:00Z",
                      "type": "session_resumed", "from_state": "blocked",
                      "to_state": "discovery", "resumed_at": "2026-09-02T20:02:00Z",
                      "resumed_by": "human",
                      "attempt_counter": {"discovery": 2},
                      "workflow_version": 1})
    journal = load_journal(jp)
    assert count_budget_transitions(journal) == 1  # only the -> blocked transition