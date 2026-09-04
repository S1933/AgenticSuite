"""C2 polarity must reach the judge (Lot 5 D5.6).

The judge must know, for each criterion, whether it is a nominal
assertion or a failure assertion (referenced by on_failure.when).
Without nature, the LLM infers from ids and passes failure criteria
that nothing in the session record supports — the Lot 5 false positive.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_suite.providers.model_evaluator import PROMPT

pytestmark = pytest.mark.session


def _criteria_for(state: dict, workflow: dict) -> list[dict]:
    """Replicates runner.py's criteria construction (C2 polarity)."""
    failure_ids = {rule.get("when") for rule in (state.get("on_failure") or [])}
    criteria: list[dict] = []
    for assertion in state.get("assertions") or []:
        criteria.append({
            "id": assertion["id"],
            "kind": "assertion",
            "nature": "failure" if assertion["id"] in failure_ids else "nominal",
            "description": str(assertion.get("description", "")),
            "evidence_from": [r for r in assertion.get("evidence_from") or []
                              if isinstance(r, str)],
        })
    for trigger in workflow.get("escalate_when") or []:
        criteria.append({
            "id": trigger["id"],
            "kind": "escalation",
            "nature": "escalation",
            "description": str(trigger.get("description", "")),
            "evidence_from": [],
        })
    return criteria


def _state() -> dict:
    return {
        "id": "investigation",
        "assertions": [
            {"id": "root_cause_is_identified", "description": "Une cause racine existe.",
             "evidence_from": ["artifacts.diagnosis", "context.root_cause_hypothesis"]},
            {"id": "no_root_cause_found", "description": "Budget épuisé sans cause.",
             "evidence_from": ["context.evidence_examined", "artifacts.diagnosis"]},
        ],
        "on_failure": [{"to": "blocked", "when": "no_root_cause_found"}],
    }


def _workflow() -> dict:
    return {"escalate_when": [{"id": "human_decision_required", "description": "Décision humaine."}]}


def test_failure_nature_derived_from_on_failure() -> None:
    criteria = _criteria_for(_state(), _workflow())
    by_id = {c["id"]: c for c in criteria}
    assert by_id["root_cause_is_identified"]["nature"] == "nominal"
    assert by_id["no_root_cause_found"]["nature"] == "failure"
    assert by_id["human_decision_required"]["nature"] == "escalation"


def test_criteria_carry_description_and_evidence() -> None:
    criteria = _criteria_for(_state(), _workflow())
    by_id = {c["id"]: c for c in criteria}
    assert by_id["root_cause_is_identified"]["description"] != ""
    assert by_id["root_cause_is_identified"]["evidence_from"] == [
        "artifacts.diagnosis", "context.root_cause_hypothesis"]


def test_prompt_contains_asymmetric_c2_rule() -> None:
    assert "Asymmetric proof" in PROMPT
    assert "failure criterion because its ID sounds plausible" in PROMPT
    assert '"nature": "failure" describes an adverse condition' in PROMPT


def test_json_payload_renders_nature() -> None:
    criteria = _criteria_for(_state(), _workflow())
    rendered = json.dumps(criteria, ensure_ascii=False, indent=2)
    assert '"nature": "failure"' in rendered
    assert '"nature": "nominal"' in rendered
    assert '"nature": "escalation"' in rendered
    assert "no_root_cause_found" in rendered