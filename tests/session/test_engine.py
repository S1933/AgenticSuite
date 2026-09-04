"""Engine — pure state machine (Lot 4a).

advance(ctx, verdict) -> Transition, with no I/O. Implements
ADR 0003 D5/D6/D7 evaluation order, C2 (polarity) and the attempt budget:

  1. escalation first: any escalate_when trigger true -> blocked
  2. failure assertions (cited by on_failure.when) in declaration order;
     the first true one triggers its on_failure target
  3. if none: exit to next: iff all checks pass AND all nominal
     assertions pass (insufficient_evidence counts as failure)
  4. otherwise: retry if attempt < max_attempts, else blocked (budget)
"""

from __future__ import annotations

import pytest

from agentic_suite.engine import (
    Transition,
    Verdict,
    advance,
)
from tests.conftest import minimal_workflow


def _wf(**overrides) -> dict:
    wf = minimal_workflow()
    # s1: next -> s2 (terminal); on_failure -> blocked on failure assertion
    wf["states"][0]["on_failure"] = [{"to": "blocked", "when": "failure_cond"}]
    wf["states"][0]["assertions"] = [
        {"id": "nominal_cond", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_cond", "description": "", "evidence_from": ["context.x"]},
    ]
    wf.update(overrides)
    return wf


def _verdict(**kw) -> Verdict:
    checks = kw.get("checks", {"x_present": True})
    assertions = kw.get("assertions", {"nominal_cond": "pass", "failure_cond": "fail"})
    escalations = kw.get("escalations", {"irreversible_action": False,
                                         "security_relevant_change": False,
                                         "human_decision_required": False,
                                         "context_contradiction": False})
    return Verdict(checks=checks, assertions=assertions, escalations=escalations)


def _ctx(wf: dict, state_id: str = "s1", attempt: int = 1,
         transitions_used: int = 0) -> dict:
    return {"workflow": wf, "state_id": state_id, "attempt": attempt,
            "transitions_used": transitions_used}


def test_nominal_exit_to_next() -> None:
    wf = _wf()
    t = advance(_ctx(wf), _verdict())
    assert t.to == "s2"
    assert t.kind == "next"


def test_failure_assertion_triggers_on_failure() -> None:
    wf = _wf()
    verdict = _verdict(assertions={"nominal_cond": "pass", "failure_cond": "pass"})
    t = advance(_ctx(wf), verdict)
    assert t.to == "blocked"
    assert t.kind == "failure"


def test_failure_assertions_evaluated_in_declaration_order() -> None:
    wf = _wf()
    wf["states"][0]["on_failure"] = [
        {"to": "reclassified", "when": "failure_a"},
        {"to": "blocked", "when": "failure_b"},
    ]
    wf["states"][0]["assertions"] = [
        {"id": "nominal_cond", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_a", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_b", "description": "", "evidence_from": ["context.x"]},
    ]
    verdict = _verdict(assertions={"nominal_cond": "pass", "failure_a": "pass",
                                   "failure_b": "pass"})
    t = advance(_ctx(wf), verdict)
    assert t.to == "reclassified"  # first true failure assertion wins


def test_insufficient_evidence_counts_as_failure() -> None:
    wf = _wf()
    verdict = _verdict(assertions={"nominal_cond": "insufficient_evidence",
                                   "failure_cond": "fail"})
    t = advance(_ctx(wf), verdict)
    assert t.to == "blocked"  # nominal failed -> budget exhausted -> blocked
    assert t.kind == "budget"


def test_retry_when_attempts_remain_and_nominal_fails() -> None:
    wf = _wf()
    wf["states"][0]["max_attempts"] = 3
    verdict = _verdict(assertions={"nominal_cond": "fail", "failure_cond": "fail"})
    t = advance(_ctx(wf, attempt=1), verdict)
    assert t.to == "s1"  # stay in state, retry
    assert t.kind == "retry"


def test_budget_blocked_when_max_attempts_reached() -> None:
    wf = _wf()
    wf["states"][0]["max_attempts"] = 2
    verdict = _verdict(assertions={"nominal_cond": "fail", "failure_cond": "fail"})
    t = advance(_ctx(wf, attempt=2), verdict)
    assert t.to == "blocked"
    assert t.kind == "budget"


def test_check_failure_blocks_nominal_exit() -> None:
    wf = _wf()
    verdict = _verdict(checks={"x_present": False})
    t = advance(_ctx(wf), verdict)  # attempt 1, max_attempts default 1
    assert t.to == "blocked"
    assert t.kind == "budget"


def test_check_failure_retries_when_budget_allows() -> None:
    wf = _wf()
    wf["states"][0]["max_attempts"] = 2
    verdict = _verdict(checks={"x_present": False})
    t = advance(_ctx(wf, attempt=1), verdict)
    assert t.kind == "retry"
    assert t.to == "s1"
    t2 = advance(_ctx(wf, attempt=2), verdict)
    assert t2.kind == "budget"
    assert t2.to == "blocked"


def test_escalation_trigger_forces_blocked() -> None:
    wf = _wf()
    verdict = _verdict(escalations={"irreversible_action": True,
                                    "security_relevant_change": False,
                                    "human_decision_required": False,
                                    "context_contradiction": False})
    t = advance(_ctx(wf), verdict)
    assert t.to == "blocked"
    assert t.kind == "escalate"


def test_escalation_wins_over_failure_assertion() -> None:
    wf = _wf()
    verdict = _verdict(
        assertions={"nominal_cond": "pass", "failure_cond": "pass"},
        escalations={"irreversible_action": False, "security_relevant_change": True,
                     "human_decision_required": False, "context_contradiction": False},
    )
    t = advance(_ctx(wf), verdict)
    assert t.to == "blocked"
    assert t.kind == "escalate"


def test_transition_budget_exceeded() -> None:
    wf = _wf()
    wf["max_transitions"] = 5
    t = advance(_ctx(wf, transitions_used=5), _verdict())
    assert t.to == "blocked"
    assert t.kind == "budget"


def test_terminal_state_has_no_transition() -> None:
    wf = minimal_workflow()
    t = advance(_ctx(wf, state_id="s2"), _verdict())
    assert t.to is None
    assert t.kind == "terminal"