"""Workflow lint rules.

Each rule is a function (workflow) -> Iterable[LintMessage]. The lint
engine calls them in order and accumulates the messages.

Rule IDs use the prefix "R" with the rule number, mapped to the relevant
ADR paragraph in the docstring of each function.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from agentic_suite.lint import error, warning


# ----- Constants from the ADRs ------------------------------------------------

# ADR 0003 D3: command_ref form
COMMAND_REF_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# ADR 0003 D3: closed set of check types
ALLOWED_CHECK_TYPES = frozenset(
    {"context_fields_present", "artifact_exists", "command_exit_zero"}
)

# ADR 0003 D8: closed set of artifact kinds
ALLOWED_KINDS = frozenset(
    {"diagnosis", "repro", "patch", "test_result", "decision", "note"}
)

# ADR 0003 D9: only two roles exist
ALLOWED_ROLES = frozenset({"actor", "evaluator"})

# ADR 0007 D3: regex for assertion names that smuggle negation.
#
# Catches the patterns that negate a pre-existing nominal assertion
# (is_not_*, does_not_*, not_*). Leaves cannot_/fails_/failed_/invalid_
# alone — those name a condition observed, not the negation of another
# assertion (cf. ADR 0007 D5 examples).
POLARITY_NEGATION_RE = re.compile(
    r"^.*_(is_not|not_|does_not)_.*$"
)

# ADR 0006 D1: skill id form (snake_case, mirror of command_ref).
SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# ----- Helpers ----------------------------------------------------------------


def _iter_states(workflow: dict) -> Iterable[tuple[str, dict]]:
    states = workflow.get("states") or []
    if not isinstance(states, list):
        return
    for i, s in enumerate(states):
        if isinstance(s, dict) and isinstance(s.get("id"), str):
            yield s["id"], s


def _assertions_by_id(state: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for a in state.get("assertions") or []:
        if isinstance(a, dict) and isinstance(a.get("id"), str):
            out[a["id"]] = a
    return out


def _is_terminal(state: dict) -> bool:
    return state.get("terminal") is True


# ----- Rules ------------------------------------------------------------------


def rule_R1_vocabulary_referenced(workflow: dict):
    """ADR 0003 D1: enum field must reference a declared vocabulary."""
    declared_vocabs = set((workflow.get("vocabularies") or {}).keys())
    for state_id, state in _iter_states(workflow):
        for i, cf in enumerate(state.get("context_fields") or []):
            if not isinstance(cf, dict):
                continue
            if cf.get("type") == "enum":
                vocab = cf.get("vocabulary")
                if vocab not in declared_vocabs:
                    yield error(
                        "R1",
                        f"states.{state_id}.context_fields[{i}].vocabulary",
                        f"enum field references undeclared vocabulary '{vocab}'",
                    )


def rule_R3_all_assertions_warning(workflow: dict):
    """ADR 0003 D2: state with no checks triggers a lint warning."""
    for state_id, state in _iter_states(workflow):
        if _is_terminal(state):
            continue
        checks = state.get("checks") or []
        assertions = state.get("assertions") or []
        if not checks and assertions:
            yield warning(
                "R3",
                f"states.{state_id}",
                "state has assertions but no checks — verify none of the "
                "conditions could be reduced to a check",
            )


def rule_R4_command_ref_format(workflow: dict):
    """ADR 0003 D3: command_ref must match [a-z][a-z0-9_]*."""
    pattern = COMMAND_REF_RE
    for state_id, state in _iter_states(workflow):
        for i, chk in enumerate(state.get("checks") or []):
            if not isinstance(chk, dict):
                continue
            if chk.get("type") == "command_exit_zero":
                ref = chk.get("command_ref")
                if isinstance(ref, str) and not pattern.match(ref):
                    yield error(
                        "R4",
                        f"states.{state_id}.checks[{i}].command_ref",
                        f"command_ref '{ref}' does not match [a-z][a-z0-9_]*",
                    )


def rule_R5_check_type_closed(workflow: dict):
    """ADR 0003 D3: check.type must be in the closed set."""
    allowed = ALLOWED_CHECK_TYPES
    for state_id, state in _iter_states(workflow):
        for i, chk in enumerate(state.get("checks") or []):
            if not isinstance(chk, dict):
                continue
            t = chk.get("type")
            if t not in allowed:
                yield error(
                    "R5",
                    f"states.{state_id}.checks[{i}].type",
                    f"check type '{t}' is not in the closed set "
                    f"{sorted(allowed)}",
                )


def rule_R6_assertion_evidence_required(workflow: dict):
    """ADR 0003 D4: every assertion must have evidence_from."""
    for state_id, state in _iter_states(workflow):
        for i, a in enumerate(state.get("assertions") or []):
            if not isinstance(a, dict):
                continue
            if "evidence_from" not in a:
                yield error(
                    "R6",
                    f"states.{state_id}.assertions[{i}]",
                    "assertion missing required field 'evidence_from'",
                )


def rule_R7_evidence_from_nonempty(workflow: dict):
    """ADR 0003 D4: evidence_from must contain at least one entry."""
    for state_id, state in _iter_states(workflow):
        for i, a in enumerate(state.get("assertions") or []):
            if not isinstance(a, dict):
                continue
            ev = a.get("evidence_from")
            if isinstance(ev, list) and len(ev) == 0:
                yield error(
                    "R7",
                    f"states.{state_id}.assertions[{i}].evidence_from",
                    "evidence_from is empty",
                )


def rule_R8_on_failure_targets_known_assertion(workflow: dict):
    """ADR 0003 D5: on_failure.when must reference a declared assertion id."""
    for state_id, state in _iter_states(workflow):
        declared = set(_assertions_by_id(state).keys())
        for i, of in enumerate(state.get("on_failure") or []):
            if not isinstance(of, dict):
                continue
            when = of.get("when")
            if isinstance(when, str) and when not in declared:
                yield error(
                    "R8",
                    f"states.{state_id}.on_failure[{i}].when",
                    f"on_failure.when '{when}' is not a declared assertion in this state",
                )


def rule_R9_escape_state_declared(workflow: dict):
    """ADR 0003 D5: targets of on_failure to escape_states must be declared."""
    declared_escapes = {
        e["id"] for e in (workflow.get("escape_states") or []) if isinstance(e, dict)
    }
    declared_states = {sid for sid, _ in _iter_states(workflow)}
    for state_id, state in _iter_states(workflow):
        for i, of in enumerate(state.get("on_failure") or []):
            if not isinstance(of, dict):
                continue
            target = of.get("to")
            if target in declared_states:
                continue
            if target not in declared_escapes:
                yield error(
                    "R9",
                    f"states.{state_id}.on_failure[{i}].to",
                    f"target state '{target}' is neither a declared state nor an escape_state",
                )


def rule_R10_reclassification_only_from_initial(workflow: dict):
    """ADR 0003 D5 (généralisé) : un terminal local cible d'un `on_failure`
    est un terminal de reclassement, atteignable uniquement depuis
    `initial_state`.

    La version originale codait en dur `reclassified` / `discovery` — le
    second workflow (`feature`) utilise `descoped` / `intake`, et la règle
    devenait silencieuse au lieu de protéger. La contrainte réelle de
    l'ADR 0003 D5 est exprimable sans nommer un état : « le terminal de
    reclassement n'est atteignable que depuis l'état initial ».
    """
    initial = workflow.get("initial_state")
    if not isinstance(initial, str):
        return  # R20 signale initial_state absent/invalide

    state_ids = {sid for sid, _ in _iter_states(workflow)}
    escape_ids = {
        e["id"] for e in (workflow.get("escape_states") or []) if isinstance(e, dict)
    }
    # Terminaux déclarés localement (hors escape_states)
    local_terminal_ids = {
        sid for sid, state in _iter_states(workflow)
        if _is_terminal(state) and sid not in escape_ids
    }

    for state_id, state in _iter_states(workflow):
        for i, of in enumerate(state.get("on_failure") or []):
            if not isinstance(of, dict):
                continue
            target = of.get("to")
            if target not in local_terminal_ids:
                continue
            # un terminal local visé par on_failure est un terminal de
            # reclassement : il n'est atteignable que depuis initial_state
            if target not in state_ids:
                continue  # R9 signale les cibles inconnues
            if state_id != initial:
                yield error(
                    "R10",
                    f"states.{state_id}.on_failure[{i}].to",
                    f"reclassification terminal '{target}' is reachable only "
                    f"from initial_state '{initial}' (ADR 0003 D5)",
                )


def _is_positive_int(value: object) -> bool:
    """True when *value* is an int but NOT a bool (bool is a subclass of int)."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def rule_R11_max_attempts_integer(workflow: dict):
    """ADR 0003 D6: max_attempts must be a positive integer."""
    for state_id, state in _iter_states(workflow):
        ma = state.get("max_attempts")
        if ma is None:
            continue
        if not _is_positive_int(ma):
            yield error(
                "R11",
                f"states.{state_id}.max_attempts",
                f"max_attempts must be a positive integer, got {ma!r}",
            )


def rule_R12_max_transitions_integer(workflow: dict):
    """ADR 0003 D6: max_transitions must be a positive integer."""
    mt = workflow.get("max_transitions")
    if mt is None:
        return
    if not _is_positive_int(mt):
        yield error(
            "R12",
            "max_transitions",
            f"max_transitions must be a positive integer, got {mt!r}",
        )


def rule_R13_escalate_when_is_assertion(workflow: dict):
    """ADR 0003 D7: escalate_when items must have nature=assertion.

    (budget_exceeded is not in escalate_when per ADR 0003 D7.)
    """
    for i, e in enumerate(workflow.get("escalate_when") or []):
        if not isinstance(e, dict):
            continue
        if e.get("nature") != "assertion":
            yield error(
                "R13",
                f"escalate_when[{i}].nature",
                "escalate_when items must have nature=assertion "
                "(budget_exceeded lives in D6, not in escalate_when)",
            )


def rule_R14_artifact_id_unique(workflow: dict):
    """ADR 0003 D8: artifact ids must be unique across the workflow."""
    seen: dict[str, str] = {}
    for state_id, state in _iter_states(workflow):
        for i, p in enumerate(state.get("produces") or []):
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            if not isinstance(pid, str):
                continue
            if pid in seen:
                yield error(
                    "R14",
                    f"states.{state_id}.produces[{i}].id",
                    f"artifact id '{pid}' is duplicated (first declared in "
                    f"states.{seen[pid]})",
                )
            else:
                seen[pid] = state_id


def rule_R15_artifact_kind_closed(workflow: dict):
    """ADR 0003 D8: artifact kind must be in the closed set."""
    allowed = ALLOWED_KINDS
    for state_id, state in _iter_states(workflow):
        for i, p in enumerate(state.get("produces") or []):
            if not isinstance(p, dict):
                continue
            kind = p.get("kind")
            if kind not in allowed:
                yield error(
                    "R15",
                    f"states.{state_id}.produces[{i}].kind",
                    f"artifact kind '{kind}' is not in the closed set "
                    f"{sorted(allowed)}",
                )


def rule_R16_evaluated_by_required_on_non_terminal(workflow: dict):
    """ADR 0003 D9 + P1: non-terminal states must declare evaluated_by."""
    allowed = ALLOWED_ROLES
    for state_id, state in _iter_states(workflow):
        if _is_terminal(state):
            continue
        ev = state.get("evaluated_by")
        if not isinstance(ev, str) or ev not in allowed:
            yield error(
                "R16",
                f"states.{state_id}.evaluated_by",
                f"non-terminal state must declare evaluated_by in {sorted(allowed)}",
            )


def rule_R17_assertion_name_polarity(workflow: dict):
    """ADR 0007 D3: assertion ids must not smuggle negation."""
    pattern = POLARITY_NEGATION_RE
    for state_id, state in _iter_states(workflow):
        for i, a in enumerate(state.get("assertions") or []):
            if not isinstance(a, dict):
                continue
            aid = a.get("id")
            if isinstance(aid, str) and pattern.match(aid):
                yield error(
                    "R17",
                    f"states.{state_id}.assertions[{i}].id",
                    f"assertion id '{aid}' uses smuggled negation; "
                    "rephrase positively (name the condition, not its negation)",
                )


def rule_R18_on_failure_assertion_exists_locally(workflow: dict):
    """ADR 0007 D4: on_failure.when must reference an assertion declared in
    the same state. (Equivalent to R8 in effect, but called by ADR 0007.)"""
    yield from rule_R8_on_failure_targets_known_assertion(workflow)


def rule_R20_initial_state_required(workflow: dict):
    """ADR 0003 P2: workflow must declare initial_state."""
    if "initial_state" not in workflow:
        yield error("R20", "initial_state", "workflow must declare 'initial_state'")
        return
    initial = workflow["initial_state"]
    state_ids = {sid for sid, _ in _iter_states(workflow)}
    escape_ids = {
        e["id"] for e in (workflow.get("escape_states") or []) if isinstance(e, dict)
    }
    if not isinstance(initial, str) or initial not in state_ids:
        # If initial_state IS an escape_state, report the escape error
        # specifically; otherwise the generic "must match a declared state"
        # error is enough.
        if initial in escape_ids:
            yield error(
                "R20",
                "initial_state",
                f"initial_state '{initial}' cannot be an escape_state",
            )
            return
        yield error(
            "R20",
            "initial_state",
            f"initial_state '{initial}' must match a declared state id",
        )
        return
    if initial in escape_ids:
        yield error(
            "R20",
            "initial_state",
            f"initial_state '{initial}' cannot be an escape_state",
        )


def rule_R21_context_evidence_attainable(workflow: dict):
    """ADR 0003 P3: context.<id> evidence must be produced by an
    attainable state on at least one path to the citing state."""
    # Map of context_field_id -> producing state_id
    producers: dict[str, str] = {}
    for sid, state in _iter_states(workflow):
        for cf in state.get("context_fields") or []:
            if isinstance(cf, dict) and isinstance(cf.get("id"), str):
                producers[cf["id"]] = sid

    # Build forward adjacency from `next` and `on_failure` for reachability
    # approximation. (Full path analysis is O(N*E) — acceptable for v0.)
    next_map: dict[str, str | None] = {}
    fail_map: dict[str, list[str]] = {}
    for sid, state in _iter_states(workflow):
        nxt = state.get("next")
        next_map[sid] = nxt if isinstance(nxt, str) else None
        targets = []
        for of in state.get("on_failure") or []:
            if isinstance(of, dict) and isinstance(of.get("to"), str):
                targets.append(of["to"])
        fail_map[sid] = targets

    def reachable(start: str) -> set[str]:
        seen: set[str] = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            nxt = next_map.get(cur)
            if nxt and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
            for t in fail_map.get(cur, []):
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        return seen

    initial = workflow.get("initial_state")
    if not isinstance(initial, str):
        return  # R20 will report

    reachable_from_start = reachable(initial)

    for state_id, state in _iter_states(workflow):
        if state_id not in reachable_from_start:
            continue
        for i, a in enumerate(state.get("assertions") or []):
            if not isinstance(a, dict):
                continue
            ev = a.get("evidence_from") or []
            if not isinstance(ev, list):
                continue
            for j, ref in enumerate(ev):
                if not isinstance(ref, str):
                    continue
                if not ref.startswith("context."):
                    continue
                field_id = ref[len("context."):]
                if field_id in producers:
                    # The field exists somewhere. Is it on a path to this state?
                    producer_state = producers[field_id]
                    if state_id in reachable(producer_state):
                        continue
                    yield error(
                        "R21",
                        f"states.{state_id}.assertions[{i}].evidence_from[{j}]",
                        f"context.{field_id} is produced by states."
                        f"{producer_state}, unreachable from there to "
                        f"states.{state_id}",
                    )
                else:
                    yield error(
                        "R21",
                        f"states.{state_id}.assertions[{i}].evidence_from[{j}]",
                        f"context.{field_id} is not declared by any state",
                    )


def rule_R22_skill_declaration(workflow: dict):
    """ADR 0006 D1: skills declared per state, {id, use_when?} entries.

    - skills must be a list of mappings with a snake_case `id`
    - `use_when` is optional free prose (a string)
    - no duplicate ids within a state
    """
    seen: set[str] = set()
    for state_id, state in _iter_states(workflow):
        skills = state.get("skills")
        if skills is None:
            continue
        if not isinstance(skills, list):
            yield error(
                "R22",
                f"states.{state_id}.skills",
                "skills must be a list of {id, use_when?} mappings",
            )
            continue
        seen.clear()
        for i, entry in enumerate(skills):
            if not isinstance(entry, dict):
                yield error(
                    "R22",
                    f"states.{state_id}.skills[{i}]",
                    "skill entry must be a mapping with an 'id'",
                )
                continue
            sid = entry.get("id")
            if not isinstance(sid, str) or not SKILL_ID_RE.match(sid):
                yield error(
                    "R22",
                    f"states.{state_id}.skills[{i}].id",
                    f"skill id must match [a-z][a-z0-9_]* (got {sid!r})",
                )
                continue
            if sid in seen:
                yield error(
                    "R22",
                    f"states.{state_id}.skills[{i}].id",
                    f"duplicate skill id '{sid}' in state",
                )
                continue
            seen.add(sid)
            uw = entry.get("use_when")
            if uw is not None and not isinstance(uw, str):
                yield error(
                    "R22",
                    f"states.{state_id}.skills[{i}].use_when",
                    "use_when must be free prose (a string)",
                )


# ----- Rule registry ----------------------------------------------------------


ALL_RULES = [
    rule_R1_vocabulary_referenced,
    rule_R3_all_assertions_warning,
    rule_R4_command_ref_format,
    rule_R5_check_type_closed,
    rule_R6_assertion_evidence_required,
    rule_R7_evidence_from_nonempty,
    rule_R8_on_failure_targets_known_assertion,
    rule_R9_escape_state_declared,
    rule_R10_reclassification_only_from_initial,
    rule_R11_max_attempts_integer,
    rule_R12_max_transitions_integer,
    rule_R13_escalate_when_is_assertion,
    rule_R14_artifact_id_unique,
    rule_R15_artifact_kind_closed,
    rule_R16_evaluated_by_required_on_non_terminal,
    rule_R17_assertion_name_polarity,
    rule_R20_initial_state_required,
    rule_R21_context_evidence_attainable,
    rule_R22_skill_declaration,
]