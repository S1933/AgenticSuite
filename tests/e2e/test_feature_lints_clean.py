"""E2E — feature.yaml v1 must pass the lint cleanly (Lot F, genericity test)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_suite.lint import engine
from agentic_suite.loader import load_workflow

pytestmark = pytest.mark.e2e

WORKFLOW_PATH = (
    Path(__file__).resolve().parent.parent.parent / "workflows" / "v1" / "feature.yaml"
)


def test_feature_v1_lints_cleanly() -> None:
    wf = load_workflow(WORKFLOW_PATH)
    msgs = engine.lint(wf)
    errors = [m for m in msgs if m.severity == "error"]
    warnings = [m for m in msgs if m.severity == "warning"]
    assert errors == [], f"errors: {errors}"
    assert warnings == [], f"warnings: {warnings}"