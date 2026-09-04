"""Orchestrator — run one state attempt end to end (Lot 4b).

The orchestrator assembles the Lot 1-2-3 pieces: it loads the session
journal, runs the deterministic checks (context/artifact/command), lets
the evaluator judge the assertions in isolation, feeds the engine, and
persists the resulting transition in the journal. Provider-agnostic: the
evaluator is injected (a mock script in tests; a real provider wired by
the CLI in Lot 4c).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from agentic_suite.session import SessionIntegrityViolation, load_journal, new_session
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.session

# A tiny evaluator scripted via env vars: reads session.jsonl from argv,
# returns verdicts from JSON on stdin. Never a real model.
MOCK_EVALUATOR = r"""
import json, os, sys

with open(sys.argv[1], encoding="utf-8") as f:
    journal_lines = len(f.read().splitlines())

criteria = json.load(sys.stdin)
verdicts = {}
for crit in criteria:
    default = "fail" if crit.get("kind") == "escalation" else "pass"
    value = os.environ.get("MOCK_VERDICT_" + crit["id"].upper(), default)
    verdicts[crit["id"]] = {"verdict": value, "evidence": "context.x"}
print(json.dumps({"verdicts": verdicts, "journal_lines": journal_lines}))
"""


@pytest.fixture
def mock_evaluator(tmp_path_factory) -> list[str]:
    script = tmp_path_factory.mktemp("eval") / "mock_eval.py"
    script.write_text(MOCK_EVALUATOR, encoding="utf-8")
    return [sys.executable, str(script)]


def _make_session(tmp_path_factory, to_state: str = "s1") -> tuple[Path, Path]:
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state=to_state, workflow_version=1)
    return jp, jdir


def _verdict_env(**verdicts: str) -> dict:
    env = dict(os.environ)
    for key, value in verdicts.items():
        env[f"MOCK_VERDICT_{key.upper()}"] = value
    return env


def _wf_with_assertions(**overrides) -> dict:
    wf = minimal_workflow()
    wf["states"][0]["assertions"] = [
        {"id": "nominal_cond", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_cond", "description": "", "evidence_from": ["context.x"]},
    ]
    wf["states"][0]["on_failure"] = [{"to": "blocked", "when": "failure_cond"}]
    wf.update(overrides)
    return wf


def test_orchestrator_nominal_run_writes_transition(tmp_path_factory, mock_evaluator) -> None:
    """Full nominal run: checks pass, assertions pass -> transition to next."""
    from agentic_suite.runner import run_attempt

    jp, jdir = _make_session(tmp_path_factory)
    (jdir / "context.json").write_text(json.dumps({"x": "value"}), encoding="utf-8")

    result = run_attempt(
        session_path=jp, session_dir=jdir, workflow=_wf_with_assertions(),
        evaluator_cmd=mock_evaluator,
        evaluator_env=_verdict_env(nominal_cond="pass", failure_cond="fail"),
    )
    assert result.transition.to == "s2"
    assert result.transition.kind == "next"

    journal = load_journal(jp)
    assert len(journal) == 2  # opened + transition
    assert journal[1]["type"] == "transition"
    assert journal[1]["to_state"] == "s2"
    assert "nominal_cond" in journal[1]["criteria_evaluated"]
    # evidence must be recorded
    assert journal[1]["evidence"]


def test_orchestrator_command_check_resolves_and_runs(tmp_path_factory, mock_evaluator) -> None:
    """command_exit_zero check resolves via .agentic/commands.yaml and runs."""
    from agentic_suite.runner import run_attempt

    proj = tmp_path_factory.mktemp("proj")
    (proj / ".agentic").mkdir()
    (proj / ".agentic" / "commands.yaml").write_text(yaml.safe_dump({
        "commands": {"run_tests": {"argv": ["true"], "timeout_seconds": 10}}
    }), encoding="utf-8")

    jp, jdir = _make_session(tmp_path_factory)
    (jdir / "context.json").write_text(json.dumps({"x": "v"}), encoding="utf-8")
    wf = _wf_with_assertions()
    wf["states"][0]["checks"] = [
        {"name": "x_present", "type": "context_fields_present",
         "fields": ["x"], "max_unknown": 0},
        {"name": "tests_pass", "type": "command_exit_zero", "command_ref": "run_tests"},
    ]
    result = run_attempt(
        session_path=jp, session_dir=jdir, workflow=wf,
        evaluator_cmd=mock_evaluator,
        evaluator_env=_verdict_env(nominal_cond="pass", failure_cond="fail"),
        project_root=proj, machine_home=None,
    )
    assert result.transition.to == "s2"
    # command output artifact recorded
    journal = result.journal
    assert any(b.get("artifact_id") == "command_output_tests_pass" for b in journal)


def test_orchestrator_failure_assertion_triggers_on_failure(tmp_path_factory, mock_evaluator) -> None:
    from agentic_suite.runner import run_attempt

    jp, jdir = _make_session(tmp_path_factory)
    (jdir / "context.json").write_text(json.dumps({"x": "v"}), encoding="utf-8")
    result = run_attempt(
        session_path=jp, session_dir=jdir, workflow=_wf_with_assertions(),
        evaluator_cmd=mock_evaluator,
        evaluator_env=_verdict_env(nominal_cond="pass", failure_cond="pass"),
    )
    assert result.transition.to == "blocked"
    assert result.transition.kind == "failure"


def test_orchestrator_budget_blocked(tmp_path_factory, mock_evaluator) -> None:
    from agentic_suite.runner import run_attempt

    jp, jdir = _make_session(tmp_path_factory)
    (jdir / "context.json").write_text(json.dumps({"x": "v"}), encoding="utf-8")
    wf = _wf_with_assertions()
    wf["states"][0]["max_attempts"] = 1
    result = run_attempt(
        session_path=jp, session_dir=jdir, workflow=wf,
        evaluator_cmd=mock_evaluator,
        evaluator_env=_verdict_env(nominal_cond="fail", failure_cond="fail"),
    )
    assert result.transition.to == "blocked"
    assert result.transition.kind == "budget"


def test_orchestrator_writes_valid_chain(tmp_path_factory, mock_evaluator) -> None:
    """The appended transition keeps the journal integrity intact."""
    from agentic_suite.runner import run_attempt

    jp, jdir = _make_session(tmp_path_factory)
    (jdir / "context.json").write_text(json.dumps({"x": "v"}), encoding="utf-8")
    result = run_attempt(
        session_path=jp, session_dir=jdir, workflow=_wf_with_assertions(),
        evaluator_cmd=mock_evaluator,
        evaluator_env=_verdict_env(nominal_cond="pass", failure_cond="fail"),
    )
    journal = load_journal(jp)
    assert len(journal) == 2
    assert result.journal == journal


def test_orchestrator_tampered_session_refused(tmp_path_factory, mock_evaluator) -> None:
    """Integrity is checked before the run: a tampered journal is refused."""
    from agentic_suite.runner import run_attempt

    jp, jdir = _make_session(tmp_path_factory)
    (jdir / "context.json").write_text(json.dumps({"x": "v"}), encoding="utf-8")
    # Tamper with the opened block
    lines = jp.read_text().splitlines()
    edited = json.loads(lines[0])
    edited["to_state"] = "done"
    lines[0] = json.dumps(edited)
    jp.write_text("\n".join(lines))
    with pytest.raises(SessionIntegrityViolation):
        run_attempt(
            session_path=jp, session_dir=jdir, workflow=_wf_with_assertions(),
            evaluator_cmd=mock_evaluator,
            evaluator_env=_verdict_env(nominal_cond="pass", failure_cond="fail"),
        )