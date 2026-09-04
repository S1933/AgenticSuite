"""Pure workflow state machine — Lot 4a.

``advance(ctx, verdict) -> Transition`` decides the next move with no I/O.
The orchestrator (Lot 4b) provides the verdict by running checks and
delegating assertions to the evaluator, then persists the transition in
the session journal.

Evaluation order (ADR 0003 D5/D7, DECISIONS C2):

1. **Escalation first.** Any ``escalate_when`` trigger judged true forces
   ``blocked`` (ADR 0003 D7). Escalation wins over every other outcome.
2. **Failure assertions** (ids cited by ``on_failure[].when``), in
   declaration order: the first one judged true triggers its
   ``on_failure`` target.
3. **Nominal exit**: if no failure assertion is true, exit to ``next``
   iff every check passes AND every *nominal* assertion passes.
   ``insufficient_evidence`` counts as a failure (burden is on the worker,
   ADR 0002).
4. **Otherwise**: retry the state if ``attempt < max_attempts``, else
   force ``blocked`` (budget exhausted, ADR 0003 D6). ``max_transitions``
   exhausted also forces ``blocked``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# Verdict values an evaluator may return for an assertion.
PASS = "pass"
FAIL = "fail"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"

# Transition kinds.
KIND_NEXT = "next"
KIND_FAILURE = "failure"
KIND_ESCALATE = "escalate"
KIND_BUDGET = "budget"
KIND_RETRY = "retry"
KIND_TERMINAL = "terminal"


@dataclass(frozen=True)
class Verdict:
    """Evaluator + runtime outcome for one state attempt."""

    checks: dict[str, bool] = field(default_factory=dict)
    # assertion_id -> pass | fail | insufficient_evidence
    assertions: dict[str, str] = field(default_factory=dict)
    # escalate_when trigger id -> judged true?
    escalations: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Transition:
    """Decision of the state machine."""

    to: Optional[str]          # None only for terminal states
    kind: str
    reason: str = ""


def _find_state(workflow: dict, state_id: str) -> Optional[dict]:
    for state in workflow.get("states") or []:
        if state.get("id") == state_id:
            return state
    return None


def _is_terminal(state: dict) -> bool:
    return bool(state.get("terminal"))


def _failure_assertion_ids(state: dict) -> set[str]:
    """Ids cited by on_failure[].when = the state's failure assertions (C2)."""
    ids: set[str] = set()
    for entry in state.get("on_failure") or []:
        when = entry.get("when")
        if isinstance(when, str):
            ids.add(when)
    return ids


def _all_checks_pass(verdict: Verdict, state: dict) -> bool:
    for chk in state.get("checks") or []:
        name = chk.get("name")
        if not isinstance(name, str) or not verdict.checks.get(name):
            return False
    return True


def _nominal_assertions_pass(verdict: Verdict, state: dict) -> bool:
    """Every assertion NOT cited by on_failure must pass."""
    failure_ids = _failure_assertion_ids(state)
    for assertion in state.get("assertions") or []:
        aid = assertion.get("id")
        if not isinstance(aid, str) or aid in failure_ids:
            continue
        if verdict.assertions.get(aid) != PASS:
            return False
    return True


def advance(ctx: dict, verdict: Verdict) -> Transition:
    """Decide the transition for the current state attempt.

    ctx keys: ``workflow`` (dict), ``state_id`` (str), ``attempt`` (int,
    1-based), ``transitions_used`` (int, budget already consumed).
    """
    workflow = ctx["workflow"]
    state_id = ctx["state_id"]
    attempt = int(ctx.get("attempt", 1))
    transitions_used = int(ctx.get("transitions_used", 0))

    state = _find_state(workflow, state_id)
    if state is None:
        return Transition("blocked", KIND_BUDGET, reason=f"unknown state {state_id}")
    if _is_terminal(state):
        return Transition(None, KIND_TERMINAL, reason="terminal state")

    max_transitions = workflow.get("max_transitions")
    if isinstance(max_transitions, int) and transitions_used >= max_transitions:
        return Transition(
            "blocked", KIND_BUDGET,
            reason=f"max_transitions {max_transitions} reached",
        )

    # 1. escalation first (ADR 0003 D7)
    for trigger in workflow.get("escalate_when") or []:
        tid = trigger.get("id")
        if isinstance(tid, str) and verdict.escalations.get(tid):
            return Transition("blocked", KIND_ESCALATE, reason=tid)

    # 2. failure assertions in declaration order (C2)
    for entry in state.get("on_failure") or []:
        when = entry.get("when")
        if isinstance(when, str) and verdict.assertions.get(when) == PASS:
            return Transition(
                entry.get("to", "blocked"), KIND_FAILURE, reason=when
            )

    # 3. nominal exit
    if _all_checks_pass(verdict, state) and _nominal_assertions_pass(verdict, state):
        return Transition(state.get("next"), KIND_NEXT, reason="criteria met")

    # 4. retry or budget-block
    max_attempts = state.get("max_attempts", 1)
    if attempt < max_attempts:
        return Transition(state_id, KIND_RETRY, reason=f"attempt {attempt} of {max_attempts}")
    return Transition(
        "blocked", KIND_BUDGET,
        reason=f"max_attempts {max_attempts} reached (attempt {attempt})",
    )