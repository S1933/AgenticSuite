"""V4-V5 — artifact_exists (ADR 0003 D3)."""

from __future__ import annotations

from agentic_suite.verification.checks import check_artifact_exists

pytestmark = __import__("pytest").mark.verification


def test_present_artifact_passes() -> None:
    artifacts = {"diagnosis": {"content": "foo"}}
    result = check_artifact_exists({"id": "diagnosis"}, artifacts)
    assert result.passed


def test_missing_artifact_fails() -> None:
    artifacts: dict = {}
    result = check_artifact_exists({"id": "diagnosis"}, artifacts)
    assert not result.passed
    assert "diagnosis" in result.detail


def test_none_artifact_value_fails() -> None:
    artifacts = {"diagnosis": None}
    result = check_artifact_exists({"id": "diagnosis"}, artifacts)
    assert not result.passed


def test_missing_id_in_definition_errors() -> None:
    artifacts = {"x": 1}
    result = check_artifact_exists({}, artifacts)
    assert not result.passed