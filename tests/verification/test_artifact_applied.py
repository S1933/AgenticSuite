"""artifact_applied check (ADR 0009) — pure function tests.

Like command_exit_zero, the pure check judges a fact provided by the
runtime (apply_result), it never performs I/O itself.
"""

from __future__ import annotations

import pytest

from agentic_suite.verification.checks import check_artifact_applied

pytestmark = pytest.mark.verification


def test_requires_id() -> None:
    res = check_artifact_applied({}, {"applied": True})
    assert res.passed is False
    assert "id" in res.detail


def test_requires_command_ref() -> None:
    res = check_artifact_applied({"id": "patch"}, {"applied": True})
    assert res.passed is False
    assert "command_ref" in res.detail


def test_unresolved_or_missing_artifact_fails() -> None:
    res = check_artifact_applied({"id": "patch", "command_ref": "apply_patch"}, None)
    assert res.passed is False
    assert "unresolved" in res.detail


def test_applied_ok() -> None:
    res = check_artifact_applied(
        {"id": "patch", "command_ref": "apply_patch"},
        {"applied": True, "detail": "exit 0"},
    )
    assert res.passed is True


def test_apply_failure_reported() -> None:
    res = check_artifact_applied(
        {"id": "patch", "command_ref": "apply_patch"},
        {"applied": False, "detail": "patch does not apply"},
    )
    assert res.passed is False
    assert "patch does not apply" in res.detail