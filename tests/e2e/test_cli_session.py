"""CLI — session lifecycle commands (Lot 4c).

agentic start <workflow>  — open a session and run until a decision
agentic status <session>  — show current state, transitions, integrity
agentic resume <session>  — resume from blocked (session_resumed)
agentic log <session>     — show the journal with invalid markers

The evaluator command is injected via AGENTIC_EVALUATOR_CMD (a mock in
tests; a real provider wired from role_assignments in a later lot).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from agentic_suite.session import new_session  # noqa: F401  (API smoke)
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.e2e

MOCK_EVALUATOR = r"""
import json, os, sys
criteria = json.load(sys.stdin)
verdicts = {}
for crit in criteria:
    default = "fail" if crit.get("kind") == "escalation" else "pass"
    value = os.environ.get("MOCK_VERDICT_" + crit["id"].upper(), default)
    verdicts[crit["id"]] = {"verdict": value, "evidence": "context.x"}
print(json.dumps({"verdicts": verdicts}))
"""


@pytest.fixture
def cli_env(tmp_path_factory, monkeypatch) -> tuple[Path, dict]:
    """A fake project with a workflow YAML, a mock evaluator, and env kwargs."""
    proj = tmp_path_factory.mktemp("proj")
    (proj / "workflows").mkdir(parents=True)
    wf = minimal_workflow()
    wf["id"] = "bugfix"
    wf["version"] = 1
    wf["initial_state"] = "s1"
    # CLI-level test: checks are the runner's concern; keep assertions only.
    # Match the mock evaluator's scripted verdicts (nominal/failure).
    wf["states"][0]["checks"] = []
    wf["states"][0]["assertions"] = [
        {"id": "nominal_cond", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_cond", "description": "", "evidence_from": ["context.x"]},
    ]
    wf["states"][0]["on_failure"] = [{"to": "blocked", "when": "failure_cond"}]
    (proj / "workflows" / "v1").mkdir()
    (proj / "workflows" / "v1" / "bugfix.yaml").write_text(
        yaml.safe_dump(wf), encoding="utf-8"
    )
    script = proj / "mock_eval.py"
    script.write_text(MOCK_EVALUATOR, encoding="utf-8")
    env = {
        "AGENTIC_EVALUATOR_CMD": f"{sys.executable} {script}",
        **{f"MOCK_VERDICT_{k.upper()}": v for k, v in {
            "nominal_cond": "pass", "failure_cond": "fail",
            "irreversible_action": "fail", "security_relevant_change": "fail",
            "human_decision_required": "fail", "context_contradiction": "fail",
        }.items()},
    }
    monkeypatch.chdir(proj)
    return proj, env


def _run_cli(cli_env: tuple[Path, dict], *args: str) -> subprocess.CompletedProcess[str]:
    proj, env = cli_env
    full_env = dict(os.environ)
    full_env.update(env)

    return subprocess.run(
        [sys.executable, "-m", "agentic_suite.cli", *args],
        cwd=str(proj), env=full_env, capture_output=True, text=True, timeout=30,
    )


def _find_session_dir(proj: Path) -> Path:
    sessions = proj / "sessions"
    dirs = [p for p in sessions.iterdir() if p.is_dir()] if sessions.exists() else []
    assert dirs, "no session dir created"
    return dirs[0]


def test_cli_start_runs_to_decision(cli_env) -> None:
    proj, _ = cli_env
    r = _run_cli(cli_env, "start", "bugfix")
    assert r.returncode == 0, r.stderr
    assert "s2" in r.stdout  # transitioned nominal -> next state
    sdir = _find_session_dir(proj)
    journal = (sdir / "session.jsonl").read_text().splitlines()
    assert len(journal) == 2  # opened + transition


def test_cli_status_shows_state_and_integrity(cli_env) -> None:
    proj, _ = cli_env
    _run_cli(cli_env, "start", "bugfix")
    sdir = _find_session_dir(proj)
    sid = sdir.name
    r = _run_cli(cli_env, "status", sid)
    assert r.returncode == 0, r.stderr
    assert "s2" in r.stdout
    assert "ok" in r.stdout.lower() or "intact" in r.stdout.lower()


def test_cli_log_lists_transitions(cli_env) -> None:
    proj, _ = cli_env
    _run_cli(cli_env, "start", "bugfix")
    sdir = _find_session_dir(proj)
    r = _run_cli(cli_env, "log", sdir.name)
    assert r.returncode == 0, r.stderr
    assert "session_opened" in r.stdout
    assert "transition" in r.stdout


def test_cli_resume_from_blocked(cli_env) -> None:
    proj, env = cli_env
    # force the run into blocked: all nominal/failure assertions fail
    env2 = {
        k: v for k, v in env.items()
        if not k.startswith("MOCK_VERDICT")
    }
    env2.update({
        "MOCK_VERDICT_NOMINAL_COND": "fail",
        "MOCK_VERDICT_FAILURE_COND": "fail",
        "MOCK_VERDICT_IRREVERSIBLE_ACTION": "fail",
        "MOCK_VERDICT_SECURITY_RELEVANT_CHANGE": "fail",
        "MOCK_VERDICT_HUMAN_DECISION_REQUIRED": "fail",
        "MOCK_VERDICT_CONTEXT_CONTRADICTION": "fail",
    })
    r = _run_cli((proj, env2), "start", "bugfix")
    assert "blocked" in r.stdout, r.stdout
    sdir = _find_session_dir(proj)
    sid = sdir.name
    r2 = _run_cli((proj, env2), "resume", sid, "s1")
    assert r2.returncode == 0, r2.stderr
    # a session_resumed block must appear (does not consume budget)
    journal = (sdir / "session.jsonl").read_text().splitlines()
    types = [json.loads(l)["type"] for l in journal]
    assert "session_resumed" in types


def test_cli_status_refuses_tampered_session(cli_env) -> None:
    proj, _ = cli_env
    _run_cli(cli_env, "start", "bugfix")
    sdir = _find_session_dir(proj)
    lines = (sdir / "session.jsonl").read_text().splitlines()
    edited = json.loads(lines[0])
    edited["to_state"] = "done"
    lines[0] = json.dumps(edited)
    (sdir / "session.jsonl").write_text("\n".join(lines))
    r = _run_cli(cli_env, "status", sdir.name)
    assert r.returncode != 0
    assert "integrity" in (r.stdout + r.stderr).lower()