"""V6-V8 — command_exit_zero (ADR 0003 D3)."""

from __future__ import annotations

from agentic_suite.verification.checks import check_command_exit_zero

pytestmark = __import__("pytest").mark.verification


def test_exit_zero_passes() -> None:
    result = check_command_exit_zero(
        {"command_ref": "run_tests"},
        {"exit_code": 0, "stdout": "", "stderr": ""},
    )
    assert result.passed


def test_exit_nonzero_fails() -> None:
    result = check_command_exit_zero(
        {"command_ref": "run_tests"},
        {"exit_code": 1, "stdout": "", "stderr": "boom"},
    )
    assert not result.passed
    assert "1" in result.detail


def test_unresolved_command_ref_fails() -> None:
    result = check_command_exit_zero({"command_ref": "run_tests"}, None)
    assert not result.passed
    assert "unresolved" in result.detail