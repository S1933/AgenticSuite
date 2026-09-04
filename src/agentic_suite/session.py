"""Session journal — ADR 0004.

An append-only JSONL journal per session. Each block carries the SHA-256
of the previous block (``prev_hash``) so any retroactive edit invalidates
the whole chain. Block hash is computed on the canonical serialization
(sorted keys, compact separators) of the block *before* ``prev_hash`` and
``hash`` are inserted.

Integrity is verified at every read (``load_journal``): a mismatch raises
:class:`SessionIntegrityViolation` and the caller is expected to move the
session to ``blocked`` with ``reason: session_integrity_violation``.

Post-hoc invalidation (ADR 0004 D5): an ``artifact_overwritten`` block
invalidates every transition whose ``evidence`` references the overwritten
artifact — the transition's proof no longer describes the artifact state
it cited (ADR 0003 D8.1).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# Canonical, minimal JSON serialization: sorted keys, no whitespace.
# Separators "," / ":" are the most compact stable choice.
_COMPACT_SEPARATORS = (",", ":")

_EMPTY_HASH = "0" * 64
_HASH_FIELDS = ("prev_hash", "hash")


class SessionIntegrityViolation(Exception):
    """Raised when the journal chain does not verify (ADR 0004 D4)."""


def canonical_bytes(obj: Any) -> bytes:
    """Serialize *obj* canonically: sorted keys, compact separators.

    This is the byte representation the ADR 0004 D3 hash is computed on.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=_COMPACT_SEPARATORS,
        ensure_ascii=False,
    ).encode("utf-8")


def block_hash(block: dict) -> str:
    """SHA-256 of the canonical block, excluding ``prev_hash``/``hash`` fields.

    The hash fields are computed after the fact; including them would make
    the hash of a stored block differ from the hash of the same block
    before storage (ADR 0004 D3).
    """
    payload = {k: v for k, v in block.items() if k not in _HASH_FIELDS}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _strip_chain_fields(block: dict) -> dict:
    """Return *block* without its stored chain fields."""
    return {k: v for k, v in block.items() if k not in _HASH_FIELDS}


def _write_block(path: Path, block: dict, prev_hash: str) -> None:
    stored = dict(block)
    stored["prev_hash"] = prev_hash
    stored["hash"] = block_hash(block)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(stored, ensure_ascii=False) + "\n")
        f.flush()
        import os

        os.fsync(f.fileno())


def new_session(path: Path, to_state: str, workflow_version: int) -> dict:
    """Write the initial ``session_opened`` block (seq=0, prev_hash = 64 zeros).

    Returns the stored block.
    """
    block = {
        "seq": 0,
        "type": "session_opened",
        "from_state": None,
        "to_state": to_state,
        "attempt_counter": {to_state: 1},
        "workflow_version": workflow_version,
    }
    _write_block(path, block, _EMPTY_HASH)
    return block


def append_block(path: Path, block: dict) -> dict:
    """Append a block (seq > 0) chained to the last stored block.

    The caller supplies all business fields; ``prev_hash`` and ``hash``
    are computed here. Returns the stored block.
    """
    if not path.exists():
        raise FileNotFoundError(f"no session journal at {path}")
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        raise ValueError(f"empty session journal at {path}")
    last = json.loads(lines[-1])
    _write_block(path, block, last["hash"])
    return block


def count_budget_transitions(blocks: list[dict]) -> int:
    """Count transitions that consume ``max_transitions`` (ADR 0003 D6).

    ADR 0004 D8: ``session_resumed`` blocks are typed separately precisely
    so the budget calculation excludes human resumes from ``blocked``.
    ``session_opened`` is not a transition either.
    """
    return sum(1 for b in blocks if b.get("type") == "transition")


def load_journal(path: Path) -> list[dict]:
    """Load and verify the journal chain (ADR 0004 D4).

    Raises :class:`SessionIntegrityViolation` on any hash mismatch or
    missing block, without attempting repair. On success, post-hoc
    invalidation (D5) is applied before returning: transitions whose
    evidence cites an artifact later overwritten are marked ``_invalid``.

    Returns a list of blocks in journal order. ``_invalid`` is a runtime
    marker, never persisted to the file.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SessionIntegrityViolation(f"cannot read journal: {exc}") from exc
    if not lines:
        raise SessionIntegrityViolation("empty journal")

    blocks: list[dict] = []
    prev_hash = _EMPTY_HASH
    expected_seq = 0
    for lineno, line in enumerate(lines, start=1):
        try:
            block = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SessionIntegrityViolation(
                f"line {lineno}: malformed JSON: {exc}"
            ) from exc
        if not isinstance(block, dict):
            raise SessionIntegrityViolation(f"line {lineno}: block is not a JSON object")
        if block.get("prev_hash") != prev_hash:
            raise SessionIntegrityViolation(
                f"line {lineno}: prev_hash mismatch (chain broken)"
            )
        if block.get("hash") != block_hash(block):
            raise SessionIntegrityViolation(
                f"line {lineno}: hash mismatch (block tampered)"
            )
        # Sequence must be contiguous 0, 1, 2, ... — a gap (or a duplicated
        # seq) means a block was dropped or spliced without a hash break.
        seq = block.get("seq")
        if seq != expected_seq:
            raise SessionIntegrityViolation(
                f"line {lineno}: seq gap (expected {expected_seq}, got {seq})"
            )
        expected_seq += 1
        blocks.append(block)
        prev_hash = block["hash"]

    # Post-hoc invalidation (ADR 0004 D5 / ADR 0003 D8.1): an overwritten
    # artifact invalidates every transition that cited it.
    overwritten = {
        b["artifact_id"]
        for b in blocks
        if b.get("type") == "artifact_overwritten"
    }
    if overwritten:
        for block in blocks:
            if block.get("type") != "transition":
                continue
            evidence = block.get("evidence") or []
            if any(
                isinstance(e, str) and e.startswith("artifacts.")
                and e.removeprefix("artifacts.") in overwritten
                for e in evidence
            ):
                block["_invalid"] = True

    return blocks