"""Check implementations.

Each check is a pure function (definition, context, ...) -> CheckResult.
No I/O. The runtime layer resolves command_ref to argv and passes the
result back here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single check execution."""

    passed: bool
    detail: str = ""


# ----- context_fields_present -------------------------------------------------


def check_context_fields_present(
    definition: dict, context: dict
) -> CheckResult:
    """ADR 0003 D3: ensure required context fields are present.

    Args:
        definition: The check definition, with keys `fields` (list[str])
            and optional `max_unknown` (int).
        context: The session context as a dict.

    Returns:
        CheckResult indicating pass/fail. Pass when at most
        `max_unknown` fields are unknown (default 0).
    """
    fields = definition.get("fields") or []
    if not isinstance(fields, list):
        return CheckResult(False, "fields must be a list")
    max_unknown = definition.get("max_unknown", 0)
    if not isinstance(max_unknown, int) or max_unknown < 0:
        return CheckResult(False, "max_unknown must be a non-negative integer")

    unknown = []
    for f in fields:
        if not isinstance(f, str):
            unknown.append(str(f))
            continue
        v = context.get(f)
        if v is None:
            unknown.append(f)
            continue
        if isinstance(v, str) and v == "":
            unknown.append(f)
            continue
        # explicit 'unknown' marker with reason counts as unknown
        # (ADR 0003 D1: "marqué inconnu avec une raison explicite")
        if isinstance(v, dict) and v.get("_unknown") is True:
            reason = v.get("_reason")
            if isinstance(reason, str) and reason.strip():
                unknown.append(f)
                continue
            # _unknown without a non-empty _reason is a malformed value,
            # not a documented unknown — it does not satisfy the field.
            return CheckResult(
                False,
                f"field '{f}' has _unknown: true but no non-empty _reason",
            )

    if len(unknown) <= max_unknown:
        return CheckResult(True, f"{len(unknown)} unknown (max {max_unknown})")
    return CheckResult(
        False,
        f"{len(unknown)} unknown fields {unknown} exceeds max_unknown {max_unknown}",
    )


# ----- artifact_exists --------------------------------------------------------


def check_artifact_exists(definition: dict, artifacts: dict) -> CheckResult:
    """ADR 0003 D3: ensure a named artifact exists in the session."""
    aid = definition.get("id")
    if not isinstance(aid, str):
        return CheckResult(False, "artifact id must be a string")
    if aid in artifacts and artifacts[aid] is not None:
        return CheckResult(True, f"artifact '{aid}' present")
    return CheckResult(False, f"artifact '{aid}' not found")


# ----- command_exit_zero ------------------------------------------------------


def check_command_exit_zero(
    definition: dict, command_output: dict[str, Any] | None
) -> CheckResult:
    """ADR 0003 D3: pass when the resolved command exit code is 0.

    The runtime resolves command_ref -> command argv and executes it.
    The result is passed here as a dict with keys `exit_code`,
    `stdout`, `stderr`, or None if the command_ref could not be resolved.
    """
    if command_output is None:
        return CheckResult(False, "command_ref unresolved")
    ec = command_output.get("exit_code")
    if ec == 0:
        return CheckResult(True, "exit 0")
    return CheckResult(False, f"exit code {ec}")