"""Skill invocation contract — ADR 0006 D4/D5.

A skill invocation is a typed session block (``skill_invoked``) carrying
a short input/output summary, appended through the normal journal chain so
integrity (ADR 0004) covers it. A skill never writes to the session itself
(D2) — it returns content to the actor, who records it via the CLI.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

# ADR 0006 D4: summaries are capped at 200 characters.
_SUMMARY_MAX = 200

# D1: skill ids are snake_case.
SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SkillInvocationError(ValueError):
    """A skill_invoked block violates ADR 0006 D4 constraints."""


def _validate_summary(value: str, field: str) -> str:
    if value is None:
        raise SkillInvocationError(f"{field} is required")
    if not isinstance(value, str):
        raise SkillInvocationError(f"{field} must be a string")
    if len(value) > _SUMMARY_MAX:
        raise SkillInvocationError(
            f"{field} exceeds {_SUMMARY_MAX} chars (got {len(value)})"
        )
    return value


def _validate_skill_id(skill_id: str) -> str:
    if not isinstance(skill_id, str) or not SKILL_ID_RE.match(skill_id):
        raise SkillInvocationError(
            f"skill_id must match [a-z][a-z0-9_]* (got {skill_id!r})"
        )
    return skill_id


def record_skill_invocation(
    journal_path: Path,
    skill_id: str,
    state_id: str,
    role: str,
    input_summary: str,
    output_summary: str,
) -> dict:
    """Append a validated ``skill_invoked`` block to *journal_path*.

    Raises :class:`SkillInvocationError` when a constraint of ADR 0006 D4
    is violated (bad skill id, role outside the closed set, summary > 200
    chars). The block is chained by :func:`agentic_suite.session.append_block`.
    """
    from agentic_suite.session import append_block

    if role not in ("actor", "evaluator"):
        raise SkillInvocationError(
            f"role must be in {{actor, evaluator}} (got {role!r})"
        )
    last = _last_seq(journal_path)
    block = {
        "seq": last + 1,
        "type": "skill_invoked",
        "skill_id": _validate_skill_id(skill_id),
        "state_id": state_id,
        "role": role,
        "input_summary": _validate_summary(input_summary, "input_summary"),
        "output_summary": _validate_summary(output_summary, "output_summary"),
    }
    return append_block(journal_path, block)


def _last_seq(journal_path: Path) -> int:
    try:
        lines = journal_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return -1
    if not lines:
        return -1
    try:
        return int(json.loads(lines[-1])["seq"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise SkillInvocationError(f"cannot read seq from {journal_path}")


def undeclared_skill_ids(
    journal: list[dict], declared: set[str]
) -> list[str]:
    """Return skill ids invoked in *journal* but absent from *declared*.

    Implements ADR 0006 D5: the runtime does not refuse an undeclared
    invocation — it records it and signals the deviation afterward. This
    helper feeds the post-execution warning (state-scoped).
    """
    flagged: list[str] = []
    for block in journal:
        if block.get("type") != "skill_invoked":
            continue
        sid = block.get("skill_id")
        if isinstance(sid, str) and sid not in declared:
            flagged.append(sid)
    return flagged