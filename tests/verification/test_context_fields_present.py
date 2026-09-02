"""V1-V3 — context_fields_present (ADR 0003 D3)."""

from __future__ import annotations

from agentic_suite.verification.checks import check_context_fields_present

pytestmark = __import__("pytest").mark.verification


def test_all_required_fields_present_passes() -> None:
    definition = {"fields": ["a", "b"], "max_unknown": 0}
    context = {"a": "x", "b": "y"}
    result = check_context_fields_present(definition, context)
    assert result.passed
    assert "0 unknown" in result.detail


def test_missing_field_fails_when_max_unknown_zero() -> None:
    definition = {"fields": ["a", "b"], "max_unknown": 0}
    context = {"a": "x"}
    result = check_context_fields_present(definition, context)
    assert not result.passed
    assert "exceeds" in result.detail


def test_missing_field_within_max_unknown_passes() -> None:
    definition = {"fields": ["a", "b", "c"], "max_unknown": 2}
    context = {"a": "x"}  # b and c missing — exactly 2 unknown
    result = check_context_fields_present(definition, context)
    assert result.passed


def test_explicit_unknown_marker_counts_as_unknown() -> None:
    definition = {"fields": ["a"], "max_unknown": 1}
    context = {"a": {"_unknown": True, "_reason": "user refused"}}
    result = check_context_fields_present(definition, context)
    assert result.passed


def test_empty_string_field_is_unknown() -> None:
    definition = {"fields": ["a"], "max_unknown": 0}
    context = {"a": ""}
    result = check_context_fields_present(definition, context)
    assert not result.passed


def test_negative_max_unknown_errors() -> None:
    definition = {"fields": ["a"], "max_unknown": -1}
    context = {"a": "x"}
    result = check_context_fields_present(definition, context)
    assert not result.passed
    assert "max_unknown" in result.detail