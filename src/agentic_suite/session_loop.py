"""Session loop — run a workflow to terminal/blocked (Lot 5.1).

Drives the actor → persist work → checks → evaluator → engine loop until
a terminal state, blocked, or a budget stop. Both the actor and the
evaluator are injected subprocesses (mock scripts in tests; real
providers via the CLI). The actor never writes the session itself: it
returns content, this module persists it through the chain (ADR 0006 D2
spirit), with artifact hashes recorded per ADR 0004 D6.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agentic_suite.engine import KIND_BUDGET, KIND_ESCALATE, KIND_FAILURE, KIND_TERMINAL
from agentic_suite.runner import _current_state, append_block, load_journal, run_attempt


@dataclass(frozen=True)
class SessionResult:
    """Outcome of a full session run."""

    final_state: str
    terminal: bool
    transitions: int = 0
    journal: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run_actor(
    actor_cmd: list[str],
    state: dict,
    context: dict,
    workflow_context: dict,
    actor_env: Optional[dict] = None,
    timeout_s: float = 300.0,   # covers actor retries (3 x LLM call)
    project_root: Optional[Path] = None,
) -> dict:
    """Call the actor subprocess; returns {"context": ..., "artifacts": ...}."""
    payload = {
        "state": state,
        "context": context,
        "workflow_context": workflow_context,
    }
    cmd = list(actor_cmd)
    if project_root is not None:
        cmd += ["--project-root", str(project_root)]
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=actor_env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"actor failed (exit {proc.returncode}): {(proc.stderr or '')[:400]}"
        )
    out = (proc.stdout or "").strip()
    try:
        result = json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"actor returned malformed JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("actor output is not an object")
    return result


def _persist_work(session_dir: Path, session_path: Path,
                  work: dict, workflow: dict, state_id: str) -> None:
    """Write actor-produced context + artifacts into the session.

    - context merges into context.json (ADR 0001: session context)
    - artifacts are written under artifacts/<id>.json with a SHA-256 hash
      and recorded as artifact_produced blocks (ADR 0004 D6)
    """
    # context
    ctx_file = session_dir / "context.json"
    if ctx_file.exists():
        try:
            existing = json.loads(ctx_file.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (OSError, json.JSONDecodeError):
            existing = {}
    else:
        existing = {}
    new_context = work.get("context") or {}
    if isinstance(new_context, dict):
        existing.update(new_context)
    ctx_file.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")

    # artifacts
    artifacts = session_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    journal = load_journal(session_path)
    seq = journal[-1]["seq"]
    produced = work.get("artifacts") or {}
    if not isinstance(produced, dict):
        raise RuntimeError("actor artifacts must be an object")
    for aid, content in produced.items():
        art_file = artifacts / f"{aid}.json"
        blob = json.dumps(content, ensure_ascii=False).encode("utf-8")
        art_file.write_bytes(blob)
        seq += 1
        append_block(session_path, {
            "seq": seq,
            "timestamp": _now_iso(),
            "type": "artifact_produced",
            "from_state": state_id,
            "to_state": state_id,
            "artifact_id": aid,
            "artifact_path": f"artifacts/{aid}.json",
            "artifact_hash": hashlib.sha256(blob).hexdigest(),
            "artifact_kind": "note",
            "attempt_counter": {},
            "workflow_version": workflow.get("version", 1),
        })


def run_session(
    session_path: Path,
    session_dir: Path,
    workflow: dict,
    actor_cmd: list[str],
    evaluator_cmd: list[str],
    actor_env: Optional[dict] = None,
    evaluator_env: Optional[dict] = None,
    project_root: Optional[Path] = None,
    machine_home: Optional[Path] = None,
    max_steps: int = 40,
) -> SessionResult:
    """Run *workflow* from the session's current state until it stops.

    The loop: determine current state → actor produces work → persist →
    checks+evaluator+engine (run_attempt) → follow the transition. Stops
    on a terminal state, blocked, or an internal step cap (safety net on
    top of max_transitions, which the engine enforces).
    """
    project_root = project_root or session_dir
    steps = 0
    while steps < max_steps:
        steps += 1
        journal = load_journal(session_path)  # verifies each iteration
        state_id = _current_state(journal)
        state = next(
            (s for s in workflow["states"] if s.get("id") == state_id), None
        )
        if state is None:
            raise ValueError(f"state '{state_id}' not found in workflow")
        if state.get("terminal"):
            return SessionResult(
                final_state=state_id, terminal=True,
                transitions=steps, journal=journal,
            )

        # 1. actor work
        context = _load_context(session_dir)
        workflow_context = _collect_workflow_context(workflow, context)
        try:
            work = _run_actor(actor_cmd, state, context, workflow_context,
                              actor_env=actor_env, project_root=project_root)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            # actor failure = cannot advance this attempt -> blocked
            append_block(session_path, {
                "seq": load_journal(session_path)[-1]["seq"] + 1,
                "timestamp": _now_iso(),
                "type": "transition",
                "from_state": state_id,
                "to_state": "blocked",
                "criteria_evaluated": [],
                "evidence": [],
                "evaluator": "actor",
                "attempt_counter": {},
                "workflow_version": workflow.get("version", 1),
            })
            journal = load_journal(session_path)
            return SessionResult(
                final_state="blocked", terminal=False,
                transitions=steps, journal=journal,
            )

        _persist_work(session_dir, session_path, work, workflow, state_id)

        # 2. checks + evaluator + engine (one attempt)
        result = run_attempt(
            session_path=session_path,
            session_dir=session_dir,
            workflow=workflow,
            evaluator_cmd=evaluator_cmd,
            evaluator_env=evaluator_env,
            project_root=project_root,
            machine_home=machine_home,
        )
        t = result.transition
        if t.kind == KIND_TERMINAL:
            return SessionResult(
                final_state=_current_state(result.journal), terminal=True,
                transitions=steps, journal=result.journal,
            )
        if t.to == "blocked" or t.kind in (KIND_BUDGET, KIND_ESCALATE, KIND_FAILURE):
            return SessionResult(
                final_state="blocked", terminal=False,
                transitions=steps, journal=result.journal,
            )
        # retry or next: loop continues from the new current state

    # safety cap (should not happen thanks to max_transitions)
    return SessionResult(
        final_state="blocked", terminal=False,
        transitions=steps, journal=load_journal(session_path),
    )


def _load_context(session_dir: Path) -> dict:
    ctx_file = session_dir / "context.json"
    try:
        raw = json.loads(ctx_file.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _collect_workflow_context(workflow: dict, context: dict) -> dict:
    """Aggregate other states' collected fields for the actor's read-only view."""
    workflow_context = {"state_ids": [s.get("id") for s in workflow["states"]]}
    workflow_context.update(context or {})
    return workflow_context