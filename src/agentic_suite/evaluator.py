"""Evaluator process isolation — ADR 0003 D9.

The evaluator is a *separate invocation with a fresh context*: it receives
only the session record (the journal) and the criteria, never the work
conversation that produced the state. This module enforces that contract
at the process boundary:

- ``run_evaluator`` copies the journal into a brand-new scratch directory,
  sets an environment containing only what is needed to execute the
  evaluator command, and runs the command with the scratch dir as cwd. The
  real session directory, its artifacts, and any conversation transcript
  are physically unreachable from the subprocess.
- ``verify_verdict_grounded`` implements the D9 semantic invariant: every
  evidence reference in the evaluator's verdict must be present in the
  session record. Evidence absent from the journal is a violation.

The evaluator command is provider-agnostic here (Lot 4 wires real agents
in). The same isolation applies.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Environment keys that could leak the session, the conversation, or
# credentials into the evaluator subprocess. Only PATH is preserved.
_ENV_BLOCKLIST = ("HERMES", "OPENAI", "ANTHROPIC", "CODEX", "TOKEN", "KEY",
                  "SECRET", "PASSWORD", "LOGNAME", "USER", "HOME", "SHELL")


@dataclass(frozen=True)
class EvaluationResult:
    """Parsed verdict of a single evaluator invocation."""

    verdicts: dict[str, dict[str, Any]]
    raw: str  # full raw stdout, kept for debugging (ADR provider result .raw)


def build_evaluator_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Minimal env for the evaluator subprocess.

    Preserves only PATH (the evaluator needs an interpreter / binaries)
    and nothing that could reference the session, the conversation, or
    credentials.
    """
    base = dict(base_env or os.environ)
    env: dict[str, str] = {}
    for key, value in base.items():
        upper = key.upper()
        if any(block in upper for block in _ENV_BLOCKLIST):
            continue
        if upper in ("PATH", "LANG", "LC_ALL", "TZ", "PYTHONIOENCODING"):
            env[key] = value
    # PYTHONIOENCODING keeps child stdout readable regardless of locale.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_evaluator(
    session_path: Path,
    criteria: list[dict],
    command: list[str],
    timeout_s: float = 60.0,
    env: dict[str, str] | None = None,
    session_dir: Path | None = None,
) -> EvaluationResult:
    """Run *command* against a copy of the session journal, in isolation.

    Args:
        session_path: The verified session journal (JSONL).
        criteria: The exit criteria the evaluator must judge.
        command: Evaluator argv (interpreter + script/args). The journal
            copy path is appended as the last positional argument — the
            evaluator reads the journal from argv; nothing else points at
            the real session.
        timeout_s: Hard kill after this many seconds.
        env: Optional extra environment fused over the minimal evaluator
            env (e.g. scripted mock verdicts in tests). Secrets in the
            caller's env are still stripped by ``build_evaluator_env``.
        session_dir: If given, the session's ``context.json`` and
            ``artifacts/`` are copied alongside the journal. The context
            fields and artifacts ARE the session record (ADR 0001), so
            the evaluator must see them to judge ``context.<id>`` /
            ``artifacts.<id>`` evidence. The work conversation is never
            copied (D9 intact).

    The subprocess cwd is a fresh scratch dir containing the session
    record: ``session.jsonl`` (always), plus ``context.json`` and
    ``artifacts/`` when *session_dir* is provided. The real session
    directory is not passed anywhere except as the source of the copy,
    and the copy path is abstracted — the evaluator can never resolve
    back to the original.
    """
    scratch = Path(tempfile.mkdtemp(prefix="agentic-eval-"))
    try:
        journal_copy = scratch / "session.jsonl"
        shutil.copy2(session_path, journal_copy)
        if session_dir is not None:
            ctx_file = session_dir / "context.json"
            if ctx_file.is_file():
                shutil.copy2(ctx_file, scratch / "context.json")
            arts = session_dir / "artifacts"
            if arts.is_dir():
                shutil.copytree(arts, scratch / "artifacts", dirs_exist_ok=True)
        # The command is a fixed argv list; the journal path is appended so
        # the evaluator locates its input without any env/cwd trickery.
        argv = list(command) + [str(journal_copy)]
        sub_env = build_evaluator_env()
        if env:
            sub_env.update({k: v for k, v in env.items()
                            if not any(b in k.upper() for b in _ENV_BLOCKLIST)})
        proc = subprocess.run(
            argv,
            cwd=str(scratch),
            env=sub_env,
            input=json.dumps(criteria),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        raw = (proc.stdout or "").strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"_raw": raw, "_stderr": (proc.stderr or "")[:500]}
        verdicts = payload.get("verdicts") if isinstance(payload, dict) else None
        if not isinstance(verdicts, dict):
            verdicts = {"_error": payload}
        return EvaluationResult(verdicts=verdicts, raw=raw)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - defensive
        return EvaluationResult(
            verdicts={"_error": {"kind": "timeout", "detail": str(exc)}},
            raw="",
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ----- invariant D9: verdict evidence must be grounded in the journal -----


def _journal_known_evidence(blocks: list[dict]) -> set[str]:
    """All evidence identifiers the session record contains.

    Covers every reference that exists in the journal: declared evidence
    on any block, produced artifact ids, and criteria evaluated. This is
    the universe an evaluator may cite.
    """
    known: set[str] = set()
    for block in blocks:
        for ev in block.get("evidence") or []:
            if isinstance(ev, str):
                known.add(ev)
        aid = block.get("artifact_id")
        if isinstance(aid, str):
            known.add(f"artifacts.{aid}")
        for crit in block.get("criteria_evaluated") or []:
            if isinstance(crit, str):
                known.add(f"checks.{crit}")
    return known


def verify_verdict_grounded(
    result: EvaluationResult, journal: list[dict]
) -> list[str]:
    """Return violations of invariant D9 for *result* against *journal*.

    Every ``evidence`` reference in the evaluator's per-criterion verdict
    must exist in the session record (ADR 0003 D9: the evaluator operates
    exclusively on the session record). A reference absent from the journal
    is a violation — the evaluator could only have gotten it from
    somewhere else (the work conversation), which the invariant forbids.

    An empty return means the invariant holds.
    """
    known = _journal_known_evidence(journal)
    violations: list[str] = []
    for criterion_id, verdict in result.verdicts.items():
        if criterion_id.startswith("_"):
            continue  # transport-level errors, not judgments
        if not isinstance(verdict, dict):
            violations.append(f"{criterion_id}: malformed verdict {verdict!r}")
            continue
        evidence = verdict.get("evidence")
        if evidence is None:
            violations.append(f"{criterion_id}: no evidence cited")
            continue
        refs = (
            evidence if isinstance(evidence, list)
            else [evidence]
        )
        for ref in refs:
            if not isinstance(ref, str) or not ref:
                violations.append(f"{criterion_id}: empty evidence reference")
                continue
            if ref not in known:
                violations.append(
                    f"{criterion_id}: evidence '{ref}' absent from session record"
                )
    return violations