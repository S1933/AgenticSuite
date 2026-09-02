"""Reusable workflow builders for lint tests."""

from __future__ import annotations

from typing import Any


def minimal_workflow(**overrides: Any) -> dict:
    """Return a minimal valid workflow that satisfies all lint rules.

    Tests override individual fields to provoke specific rule violations.
    """
    base: dict = {
        "id": "wf",
        "version": 1,
        "initial_state": "s1",
        "max_transitions": 20,
        "escape_states": [
            {"id": "blocked", "terminal": False},
            {"id": "abandoned", "terminal": True},
        ],
        "escalate_when": [
            {"id": "irreversible_action", "nature": "assertion"},
            {"id": "security_relevant_change", "nature": "assertion"},
            {"id": "human_decision_required", "nature": "assertion"},
            {"id": "context_contradiction", "nature": "assertion"},
        ],
        "states": [
            {
                "id": "s1",
                "role": "actor",
                "evaluated_by": "evaluator",
                "max_attempts": 1,
                "context_fields": [
                    {"id": "x", "type": "text", "required": True, "description": ""}
                ],
                "checks": [
                    {
                        "name": "x_present",
                        "type": "context_fields_present",
                        "fields": ["x"],
                        "max_unknown": 0,
                    }
                ],
                "assertions": [
                    {
                        "id": "x_is_set",
                        "description": "x has been set",
                        "evidence_from": ["context.x"],
                    }
                ],
                "produces": [{"id": "note_a", "kind": "note", "required": True}],
                "next": "s2",
                "on_failure": [{"to": "blocked", "when": "x_is_set"}],
            },
            {
                "id": "s2",
                "role": "actor",
                "evaluated_by": "evaluator",
                "max_attempts": 1,
                "terminal": True,
            },
        ],
    }
    base.update(overrides)
    return base


def by_path(workflow: dict, *path: str | int) -> Any:
    """Traverse a workflow by dotted/index path. Helper for assertions."""
    cur: Any = workflow
    for p in path:
        cur = cur[p]
    return cur