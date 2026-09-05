"""Orchestrator — run one state attempt end to end (Lot 4b).

Assembles the Lot 1-2-3 pieces around the pure engine:

1. load + verify the session journal (ADR 0004 D4)
2. determine the current state from the last block
3. run deterministic checks (context_fields_present, artifact_exists,
   command_exit_zero with command_ref resolution)
4. let the evaluator judge the assertions AND the escalation triggers
   (ADR 0003 D7: always a distinct evaluator; ADR 0005 provider)
5. feed the engine and persist the resulting transition in the journal

The evaluator is injected (command + env) so tests use a mock and the
CLI wires a real provider. No real model is ever called by the tests.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from agentic_suite.commands import resolve_command_ref
from agentic_suite.engine import KIND_TERMINAL, Verdict, advance
from agentic_suite.evaluator import run_evaluator
from agentic_suite.session import append_block, load_journal
from agentic_suite.verification.checks import (
    check_artifact_applied,
    check_artifact_exists,
    check_command_exit_zero,
    check_context_fields_present,
)


@dataclass(frozen=True)
class RunResult:
    """Outcome of one state attempt."""

    transition: Any          # engine.Transition
    journal: list[dict]      # blocks as persisted (reloaded)


def _current_state(journal: list[dict]) -> str:
    """ADR 0004 D1: current state = to_state of last valid block."""
    return str(journal[-1].get("to_state") or "")


def _attempt_count(journal: list[dict], state_id: str) -> int:
    """ADR 0004 D7: attempt counter incremented on state entry.

    Count open/transition blocks whose to_state == state_id (each entry
    into the state counts). session_opened counts as entry 1.
    """
    return sum(
        1
        for b in journal
        if b.get("to_state") == state_id
        and b.get("type") in ("session_opened", "transition", "session_resumed")
    )


def _transitions_used(journal: list[dict]) -> int:
    """ADR 0003 D6 + ADR 0004 D8: transitions consuming the budget.

    session_resumed (human resume from blocked) is excluded by typology.
    """
    return sum(
        1 for b in journal if b.get("type") == "transition"
    )


def _load_context(session_dir: Path) -> dict:
    ctx_file = session_dir / "context.json"
    try:
        raw = json.loads(ctx_file.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _load_artifacts(session_dir: Path) -> dict:
    """Index artifacts from the journal: {artifact_id: {"path": ..., "hash": ...}}."""
    artifacts: dict[str, dict] = {}
    journal = load_journal(session_dir / "session.jsonl")
    for block in journal:
        if block.get("type") in ("artifact_produced", "artifact_overwritten"):
            aid = block.get("artifact_id")
            if isinstance(aid, str):
                artifacts[aid] = {"path": block.get("artifact_path"),
                                  "hash": block.get("artifact_hash")}
    return artifacts


def _run_checks(
    state: dict,
    context: dict,
    artifacts: dict,
    project_root: Path,
    machine_home: Optional[Path],
    session_dir: Path,
) -> tuple[dict[str, bool], list[dict]]:
    """Execute deterministic checks; returns (pass_map, command_artifacts).

    command_exit_zero resolves the ref (ADR 0005 D5) and runs argv without
    a shell. Output is captured into an implicit artifact
    ``command_output_<check_name>`` (ADR 0003 D3).
    """
    results: dict[str, bool] = {}
    command_artifacts: list[dict] = []
    for chk in state.get("checks") or []:
        name = chk.get("name")
        ctype = chk.get("type")
        if ctype == "context_fields_present":
            res = check_context_fields_present(chk, context)
        elif ctype == "artifact_exists":
            res = check_artifact_exists(chk, artifacts)
        elif ctype == "command_exit_zero":
            ref = chk.get("command_ref")
            resolved = resolve_command_ref(project_root, ref, machine_home)
            if resolved is None:
                res = check_command_exit_zero(chk, None)  # command_ref_unresolved
            else:
                output = _execute_command(resolved, session_dir)
                output["check_name"] = name
                command_artifacts.append(output)
                res = check_command_exit_zero(chk, output)
        elif ctype == "artifact_applied":  # ADR 0009 D1
            apply_result = _apply_artifact(chk, artifacts, session_dir,
                                           project_root, machine_home)
            res = check_artifact_applied(chk, apply_result)
        else:
            res = check_artifact_exists(chk, artifacts)  # unknown type: fail
        results[name] = res.passed
    return results, command_artifacts


def _application_content(raw: str) -> Optional[str]:
    """Extract the diff text from an artifact's stored content.

    Artifacts are persisted as JSON (session D6). A patch artifact is
    stored as ``json.dumps(diff_string)``; some producers keep a dict
    with a 'patch' or 'diff' key. Returns the diff text, or None if the
    content is not a string anywhere (never a guess).
    """
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return raw  # plain text artifact
    if isinstance(decoded, str):
        return decoded
    if isinstance(decoded, dict):
        for key in ("patch", "diff", "content"):
            value = decoded.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _apply_artifact(
    definition: dict,
    artifacts: dict,
    session_dir: Path,
    project_root: Path,
    machine_home: Optional[Path],
) -> Optional[dict]:
    """ADR 0009 D1: materialise the artifact and apply it to the tree.

    Resolution: the artifact id must exist in the session; the command_ref
    is resolved like command_exit_zero (project > machine, ADR 0005 D5).
    The artifact content (a diff) is written to ``<session>/tmp/<id>.diff``
    and the resolved argv is executed with the diff path appended, with
    cwd = project_root (the WORKING TREE, not the session dir).

    Returns a fact dict for the pure check, or None when the artifact is
    absent or the command_ref unresolved.
    """
    aid = definition.get("id")
    if not isinstance(aid, str) or aid not in artifacts:
        return None
    ref = definition.get("command_ref")
    resolved = resolve_command_ref(project_root, ref, machine_home)
    if resolved is None:
        return None

    artifact_path = Path(artifacts[aid]["path"]) if artifacts[aid].get("path") else None
    if artifact_path is None or not artifact_path.is_file():
        return None
    try:
        raw = artifact_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"applied": False, "detail": f"cannot read artifact: {exc}"}
    content = _application_content(raw)
    if content is None:
        return {"applied": False,
                "detail": "artifact content is not a diff (no string)"}
    if not content.strip():
        return {"applied": False, "detail": "artifact content is empty"}

    tmp_dir = session_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    diff_file = tmp_dir / f"{aid}.diff"
    try:
        diff_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {"applied": False, "detail": f"cannot materialise diff: {exc}"}

    argv = list(resolved["argv"]) + [str(diff_file)]
    timeout = resolved.get("timeout_seconds", 60)
    try:
        proc = subprocess.run(
            argv, cwd=str(project_root), capture_output=True, text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"applied": False, "detail": str(exc)}
    if proc.returncode == 0:
        return {"applied": True, "detail": "exit 0"}
    detail = (proc.stderr or proc.stdout or "").strip()[:500]
    return {"applied": False, "detail": detail or f"exit {proc.returncode}"}


def _execute_command(definition: dict, session_dir: Path) -> dict:
    """Run argv without a shell (ADR 0005 D5), capture stdout/stderr/exit."""
    argv = definition["argv"]
    timeout = definition.get("timeout_seconds", 60)
    cwd = definition.get("cwd")
    workdir = (session_dir / cwd).resolve() if cwd else session_dir
    try:
        proc = subprocess.run(
            argv, cwd=str(workdir), capture_output=True, text=True, timeout=timeout,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": (proc.stdout or "")[:2000],
            "stderr": (proc.stderr or "")[:2000],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit_code": -1, "stdout": "", "stderr": str(exc)}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_attempt(
    session_path: Path,
    session_dir: Path,
    workflow: dict,
    evaluator_cmd: list[str],
    evaluator_env: dict | None = None,
    project_root: Optional[Path] = None,
    machine_home: Optional[Path] = None,
) -> RunResult:
    """Run one attempt of the current state and persist the transition.

    Raises SessionIntegrityViolation on a tampered journal (integrity is
    checked BEFORE anything is executed or written).
    """
    project_root = project_root or session_dir
    journal = load_journal(session_path)  # verifies (ADR 0004 D4)
    state_id = _current_state(journal)
    state = next((s for s in workflow["states"] if s.get("id") == state_id), None)
    if state is None:
        raise ValueError(f"state '{state_id}' not found in workflow")
    if state.get("terminal"):
        return RunResult(
            transition=advance(
                {"workflow": workflow, "state_id": state_id,
                 "attempt": 1, "transitions_used": 0},
                Verdict(),
            ),
            journal=journal,
        )

    context = _load_context(session_dir)
    artifacts = _load_artifacts(session_dir)

    # 1. deterministic checks
    check_results, command_artifacts = _run_checks(
        state, context, artifacts, project_root, machine_home, session_dir
    )

    # 2. evaluator judges assertions + escalation triggers (distinct evaluator)
    #    Criteria carry the full contract so the judge never infers from ids:
    #    description, evidence_from, and C2 polarity (nature = failure for
    #    assertions referenced by on_failure.when — ADR 0002 conventions).
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

    eval_result = run_evaluator(
        session_path=session_path,
        criteria=criteria,
        command=evaluator_cmd,
        timeout_s=300,  # covers judge retries (3 x LLM call) without killing them
        env=evaluator_env,
        session_dir=session_dir,
    ) if criteria else None

    assertions: dict[str, str] = {}
    escalations: dict[str, bool] = {}
    if eval_result is not None:
        for crit in criteria:
            verdict = eval_result.verdicts.get(crit["id"], {})
            value = verdict.get("verdict", "fail") if isinstance(verdict, dict) else "fail"
            if crit["kind"] == "escalation":
                escalations[crit["id"]] = value == "pass"
            else:
                assertions[crit["id"]] = value

    # 3. engine decides
    verdict = Verdict(checks=check_results, assertions=assertions,
                      escalations=escalations)
    ctx = {
        "workflow": workflow,
        "state_id": state_id,
        "attempt": _attempt_count(journal, state_id),
        "transitions_used": _transitions_used(journal),
    }
    transition = advance(ctx, verdict)

    # 4. persist: command output artifacts then the transition block
    seq = journal[-1]["seq"]
    for artifact in command_artifacts:
        # implicit command_output_<check> artifacts (ADR 0003 D3)
        checkpoint = artifact.get("check_name") or "check"
        seq += 1
        aid = f"command_output_{checkpoint}"
        append_block(session_path, {
            "seq": seq,
            "timestamp": _now_iso(),
            "type": "artifact_produced",
            "from_state": state_id,
            "to_state": state_id,
            "artifact_id": aid,
            "artifact_path": "",
            "artifact_hash": "",
            "artifact_kind": "test_result",
            "attempt_counter": {state_id: _attempt_count(journal, state_id)},
            "workflow_version": workflow.get("version", 1),
        })

    if transition.kind != KIND_TERMINAL:
        evidence = _collect_evidence(state, assertions)
        seq += 1
        all_verdicts: dict[str, str] = {}
        for crit in criteria:
            v = "fail"
            if crit["kind"] == "escalation":
                v = "pass" if escalations.get(crit["id"]) else "fail"
            else:
                v = assertions.get(crit["id"], "fail")
            all_verdicts[crit["id"]] = v
        append_block(session_path, {
            "seq": seq,
            "timestamp": _now_iso(),
            "type": "transition",
            "from_state": state_id,
            "to_state": transition.to,
            "criteria_evaluated": sorted(assertions.keys()),
            "criteria_verdicts": all_verdicts,   # Lot 5 D5.5 — auditer les verdicts
            "evidence": evidence,
            "evaluator": "evaluator",
            "attempt_counter": {state_id: _attempt_count(journal, state_id)},
            "workflow_version": workflow.get("version", 1),
        })

    reloaded = load_journal(session_path)
    return RunResult(transition=transition, journal=reloaded)


def _collect_evidence(state: dict, assertions: dict[str, str]) -> list[str]:
    """Evidence referenced by the assertions that were evaluated true."""
    evidence: list[str] = []
    for assertion in state.get("assertions") or []:
        aid = assertion.get("id")
        if isinstance(aid, str) and assertions.get(aid) in ("pass", "insufficient_evidence"):
            for ref in assertion.get("evidence_from") or []:
                if isinstance(ref, str):
                    evidence.append(ref)
    return evidence