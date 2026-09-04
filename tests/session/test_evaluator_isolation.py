"""Evaluator process isolation — ADR 0003 D9.

The evaluator must operate exclusively on the session record, never on
the work conversation that produced the state. Two layers are tested:

  - process isolation (Lot 1.3): the evaluator subprocess receives ONLY a
    copy of the session journal in an empty scratch dir — no session
    directory, no artifacts, no conversation file, minimal env.
  - semantic grounding (Lot 1.2, invariant D9): every evidence reference
    in the evaluator's verdict must exist in the session record. A verdict
    citing anything absent is a violation.

The evaluator used here is the mock evaluator script (never a real model):
the rule "CI never calls a real model" (README testing strategy) applies
to the evaluator the same way it applies to providers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_suite.evaluator import (
    EvaluationResult,
    build_evaluator_env,
    run_evaluator,
    verify_verdict_grounded,
)
from agentic_suite.session import new_session

pytestmark = pytest.mark.session

MOCK_EVALUATOR = r'''
import json, os, sys

with open("session.jsonl", encoding="utf-8") as f:
    journal = f.read()

criteria = json.load(sys.stdin)

# Probe what the process can see that it must NOT see.
leaks = []
probes = ["conversation.txt", "../session.jsonl", "artifacts"]
for name in probes:
    if os.path.exists(name):
        leaks.append(name)

verdicts = {}
for crit in criteria:
    verdicts[crit["id"]] = {"verdict": "pass",
                            "evidence": crit.get("expected_evidence", "context.x")}

print(json.dumps({
    "verdicts": verdicts,
    "journal_lines": len(journal.splitlines()),
    "seen_argv": sys.argv,
    "leaks": leaks,
}))
'''


def _make_session(tmp_path_factory) -> Path:
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    return jp


def _write_conversation_near_session(jp: Path) -> Path:
    """A fake work-conversation transcript sitting next to the session dir."""
    conv = jp.parent.parent / "conversation.txt"
    conv.write_text("working notes that the evaluator must never see", encoding="utf-8")
    return conv


def _criteria(*ids: str) -> list[dict]:
    return [{"id": cid} for cid in ids]


def _run_mock(jp: Path, criteria: list[dict]) -> EvaluationResult:
    import sys

    return run_evaluator(
        session_path=jp,
        criteria=criteria,
        command=[sys.executable, "-c", MOCK_EVALUATOR],
        timeout_s=15,
    )


def test_evaluator_env_is_minimal(tmp_path_factory) -> None:
    """The evaluator must not inherit session/agent env (no HERMES_*, no LOGNAME)."""
    env = build_evaluator_env({"HERMES_HOME": "/secret", "OPENAI_API_KEY": "k",
                               "PATH": "/usr/bin:/bin", "HOME": "/home/pi"})
    assert "HERMES_HOME" not in env
    assert "OPENAI_API_KEY" not in env
    assert "HOME" not in env
    assert env.get("PATH")  # the evaluator needs an interpreter


def test_evaluator_gets_only_journal_copy(tmp_path_factory) -> None:
    """Lot 1.3: the subprocess cwd contains only session.jsonl — no artifacts,
    no conversation, no access back to the real session directory."""
    jp = _make_session(tmp_path_factory)
    conv = _write_conversation_near_session(jp)
    assert conv.exists()

    result = _run_mock(jp, _criteria("c1"))
    payload = json.loads(result.raw)

    assert payload["leaks"] == [], f"evaluator saw leaked paths: {payload['leaks']}"
    assert payload["journal_lines"] == 1
    # argv must not contain paths pointing at the real session dir
    assert str(jp.parent) not in " ".join(payload["seen_argv"])


def test_evaluator_verdict_must_be_grounded_in_journal(tmp_path_factory) -> None:
    """Lot 1.2 (invariant D9): evidence cited by the verdict must exist in the
    session record. Evidence absent from the journal is a violation."""
    jp = _make_session(tmp_path_factory)
    # evaluator cites evidence the session never recorded
    result = _run_mock(
        jp,
        [{"id": "c1", "expected_evidence": "artifacts.phantom_diagnosis"}],
    )
    journal = [{"type": "session_opened", "evidence": []}]
    violations = verify_verdict_grounded(result, journal)
    assert violations  # phantom evidence must be flagged


def test_grounded_verdict_passes_invariant(tmp_path_factory) -> None:
    """Evidence the session recorded is accepted; the invariant holds."""
    jp = _make_session(tmp_path_factory)
    journal = [
        {"type": "session_opened", "evidence": []},
        {"type": "artifact_produced", "artifact_id": "diagnosis",
         "evidence": ["artifacts.diagnosis"]},
    ]
    result = _run_mock(jp, [{"id": "c1", "expected_evidence": "artifacts.diagnosis"}])
    violations = verify_verdict_grounded(result, journal)
    assert violations == []


def test_verdict_citing_context_absent_is_violation(tmp_path_factory) -> None:
    """Evidence pointing at a context field the session never collected is absent."""
    jp = _make_session(tmp_path_factory)
    journal = [{"type": "session_opened", "evidence": []}]
    result = _run_mock(jp, [{"id": "c1", "expected_evidence": "context.root_cause"}])
    violations = verify_verdict_grounded(result, journal)
    assert any("context.root_cause" in v for v in violations)