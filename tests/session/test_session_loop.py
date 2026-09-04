"""Session loop — run a workflow to a terminal/blocked state (Lot 5.1).

run_session drives the actor/work/evaluator/judge/engine loop until:
  - a terminal state (done, reclassified, descoped, abandoned) — success
  - blocked (escalation, budget, failure assertion) — needs a human
  - max_transitions exhausted

The actor produces context+artifacts, the runner persists them, the
evaluator judges, the engine decides. Both are injected (mock scripts in
tests; real providers via CLI). No real model in CI.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from agentic_suite.engine import KIND_BUDGET, KIND_ESCALATE, KIND_FAILURE, KIND_TERMINAL
from agentic_suite.session import append_block, load_journal, new_session
from tests.conftest import minimal_workflow

pytestmark = pytest.mark.session

MOCK_ACTOR = r"""
import json, os, sys
payload = json.load(sys.stdin)
state = payload["state"]
sid = state["id"]
# fill required text fields with placeholder values; artifacts per state
context = {}
for cf in state.get("context_fields") or []:
    if cf["required"]:
        kind = cf["type"]
        if kind == "list":
            context[cf["id"]] = ["item"]
        elif kind == "enum":
            context[cf["id"]] = "allowed_value"
        else:
            context[cf["id"]] = f"value-for-{cf['id']}"
artifacts = {}
for pr in state.get("produces") or []:
    if pr["required"]:
        artifacts[pr["id"]] = {"content": f"{pr['id']}-content"}
print(json.dumps({"context": context, "artifacts": artifacts}))
"""

MOCK_EVALUATOR = r"""
import json, os, sys
criteria = json.load(sys.stdin)
verdicts = {}
for crit in criteria:
    default = "fail" if crit.get("kind") == "escalation" else "pass"
    verdicts[crit["id"]] = {"verdict": os.environ.get(
        "MOCK_VERDICT_" + crit["id"].upper(), default), "evidence": "context.x"}
print(json.dumps({"verdicts": verdicts}))
"""


@pytest.fixture
def mocks(tmp_path_factory) -> dict:
    """Paths + env for mock actor & evaluator scripts."""
    d = tmp_path_factory.mktemp("mocks")
    actor_script = d / "actor.py"
    actor_script.write_text(MOCK_ACTOR, encoding="utf-8")
    eval_script = d / "eval.py"
    eval_script.write_text(MOCK_EVALUATOR, encoding="utf-8")
    env = {
        "MOCK_VERDICT_NOMINAL_COND": "pass",
        "MOCK_VERDICT_FAILURE_COND": "fail",
        **{f"MOCK_VERDICT_{t.upper()}": "fail" for t in
           ("irreversible_action", "security_relevant_change",
            "human_decision_required", "context_contradiction")},
    }
    return {
        "actor_cmd": [sys.executable, str(actor_script)],
        "evaluator_cmd": [sys.executable, str(eval_script)],
        "env": env,
    }


def _session(tmp_path_factory) -> tuple[Path, Path]:
    jdir = tmp_path_factory.mktemp("sess")
    jp = jdir / "session.jsonl"
    new_session(jp, to_state="s1", workflow_version=1)
    return jp, jdir


def _wf() -> dict:
    wf = minimal_workflow()
    wf["id"] = "bugfix"
    wf["version"] = 1
    wf["max_transitions"] = 10
    wf["initial_state"] = "s1"
    wf["states"][0]["assertions"] = [
        {"id": "nominal_cond", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_cond", "description": "", "evidence_from": ["context.x"]},
    ]
    wf["states"][0]["on_failure"] = [{"to": "blocked", "when": "failure_cond"}]
    wf["states"][1]["max_attempts"] = 1
    wf["states"][1]["assertions"] = [
        {"id": "nominal_cond", "description": "", "evidence_from": ["context.x"]},
        {"id": "failure_cond", "description": "", "evidence_from": ["context.x"]},
    ]
    wf["states"][1]["on_failure"] = [{"to": "blocked", "when": "failure_cond"}]
    wf["states"][1]["terminal"] = False  # intermediate -> done
    wf["states"][1]["next"] = "done"
    wf["states"].append({"id": "done", "terminal": True})
    # s1 produces a required artifact so the mock actor has something to write
    wf["states"][0]["produces"] = [{"id": "worknote", "kind": "note", "required": True}]
    return wf


def test_run_session_reaches_terminal(mocks, tmp_path_factory) -> None:
    """mock actor fills everything, evaluator passes -> s1 -> s2 -> done."""
    from agentic_suite.session_loop import run_session

    jp, jdir = _session(tmp_path_factory)
    result = run_session(
        session_path=jp, session_dir=jdir, workflow=_wf(),
        actor_cmd=mocks["actor_cmd"], evaluator_cmd=mocks["evaluator_cmd"],
        actor_env=mocks["env"], evaluator_env=mocks["env"],
    )
    assert result.final_state == "done"
    assert result.terminal is True
    journal = load_journal(jp)
    types = [b.get("to_state") for b in journal]
    assert "done" in types


def test_run_session_records_context_and_artifacts(mocks, tmp_path_factory) -> None:
    from agentic_suite.session_loop import run_session

    jp, jdir = _session(tmp_path_factory)
    run_session(
        session_path=jp, session_dir=jdir, workflow=_wf(),
        actor_cmd=mocks["actor_cmd"], evaluator_cmd=mocks["evaluator_cmd"],
        actor_env=mocks["env"], evaluator_env=mocks["env"],
    )
    # the actor's produced artifact must be persisted as artifact blocks
    journal = load_journal(jp)
    artifact_blocks = [b for b in journal if b.get("type") == "artifact_produced"]
    assert any(b.get("artifact_id") == "worknote" for b in artifact_blocks)


def test_run_session_blocked_on_failure_assertion(mocks, tmp_path_factory) -> None:
    """Evaluator flips failure_cond -> blocked, loop stops."""
    from agentic_suite.session_loop import run_session

    jp, jdir = _session(tmp_path_factory)
    env = dict(mocks["env"])
    env["MOCK_VERDICT_FAILURE_COND"] = "pass"
    result = run_session(
        session_path=jp, session_dir=jdir, workflow=_wf(),
        actor_cmd=mocks["actor_cmd"], evaluator_cmd=mocks["evaluator_cmd"],
        actor_env=env, evaluator_env=env,
    )
    assert result.final_state == "blocked"
    assert result.terminal is False


def test_run_session_stops_on_max_transitions(mocks, tmp_path_factory) -> None:
    """Budget: retry in loop with a tiny max_transitions must stop at blocked."""
    from agentic_suite.session_loop import run_session

    jp, jdir = _session(tmp_path_factory)
    wf = _wf()
    wf["max_transitions"] = 2
    # make the evaluator always fail -> loop retries -> budget exhausted
    env = {k: ("fail" if k.startswith("MOCK_VERDICT") else v)
           for k, v in mocks["env"].items()}
    result = run_session(
        session_path=jp, session_dir=jdir, workflow=wf,
        actor_cmd=mocks["actor_cmd"], evaluator_cmd=mocks["evaluator_cmd"],
        actor_env=env, evaluator_env=env,
    )
    assert result.final_state == "blocked"
    assert result.terminal is False
    # loop must not spin forever beyond the budget
    journal = load_journal(jp)
    assert len(journal) <= 8  # well under a spin-a-way count