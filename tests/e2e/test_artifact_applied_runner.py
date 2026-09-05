"""artifact_applied end-to-end (ADR 0009) — real git repo, real apply.

Verifies that run_attempt applies the artifact to the WORKING TREE
(cwd = project_root) before later checks run, and that a valid diff
passes while an inapplicable one fails. Creates a real git repo.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from agentic_suite.runner import run_attempt, _apply_artifact
from agentic_suite.session import append_block, new_session

pytestmark = pytest.mark.e2e


def _git_repo(tmp_path: Path) -> Path:
    """Init a git repo with a buggy sizes.py (the Lot 5 scratch bug)."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    src = tmp_path / "sizes.py"
    src.write_text(
        "def format_bytes(num, binary=False):\n"
        "    if num < 1024 or binary is False:\n"
        "        return f'{num} B'\n"
        "    return '1.0 KiB'\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "sizes.py"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=test",
         "-c", "user.email=test@example.com", "commit", "-q", "-m", "buggy"],
        check=True, env=None,
    )
    return tmp_path


def _session_with_patch(root: Path, patch_content: str) -> Path:
    sdir = root / "sessions" / "s-test"
    sdir.mkdir(parents=True)
    jp = sdir / "session.jsonl"
    new_session(jp, to_state="fix", workflow_version=1)
    patch_path = sdir / "artifacts" / "patch.json"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    patch_path.write_text(json.dumps(patch_content), encoding="utf-8")
    append_block(jp, {
        "seq": 1, "timestamp": "t", "type": "artifact_produced",
        "from_state": "fix", "to_state": "fix",
        "artifact_id": "patch", "artifact_path": str(patch_path),
        "artifact_hash": "", "artifact_kind": "patch",
        "attempt_counter": {"fix": 1}, "workflow_version": 1,
    })
    append_block(jp, {
        "seq": 2, "timestamp": "t", "type": "transition",
        "from_state": "fix", "to_state": "validation",
        "criteria_verdicts": {}, "workflow_version": 1,
    })
    return sdir


def _workflow() -> dict:
    return {
        "version": 1,
        "id": "bugfix",
        "initial_state": "validation",
        "states": [
            {
                "id": "validation",
                "role": "actor",
                "max_attempts": 1,
                "checks": [
                    {"name": "patch_applied", "type": "artifact_applied",
                     "id": "patch", "command_ref": "apply_patch"},
                ],
                "assertions": [],
                "produces": [],
                "next": "done",
            },
            {"id": "done", "terminal": True},
        ],
    }


@pytest.fixture()
def apply_patch_cmd(monkeypatch, tmp_path: Path) -> None:
    """Wire a project-level apply_patch command for the temp repo."""
    agentic_dir = tmp_path / ".agentic"
    agentic_dir.mkdir(exist_ok=True)
    (agentic_dir / "commands.yaml").write_text(
        "commands:\n"
        "  apply_patch:\n"
        "    argv: [git, apply, --whitespace=nowarn]\n",
        encoding="utf-8",
    )


def _make_patch(tmp_path: Path) -> tuple[Path, str]:
    """Apply a real fix, capture `git diff`, then revert — a TRUE diff."""
    src = tmp_path / "sizes.py"
    fixed = (
        "def format_bytes(num, binary=False):\n"
        "    if num < 1024 or binary is False:\n"
        "        # fixed\n"
        "        return f'{num} B'\n"
    )
    src.write_text(fixed, encoding="utf-8")
    diff = subprocess.run(
        ["git", "-C", str(tmp_path), "diff"], capture_output=True, text=True, check=True
    ).stdout
    # revert to the buggy state so the apply actually changes the tree
    subprocess.run(["git", "-C", str(tmp_path), "checkout", "--", "sizes.py"], check=True)
    assert "fixed" not in src.read_text(encoding="utf-8")
    return tmp_path, diff


def test_apply_artifact_modifies_working_tree(tmp_path: Path, apply_patch_cmd) -> None:
    root = _git_repo(tmp_path)
    _, diff = _make_patch(root)
    sdir = _session_with_patch(root, diff)

    result = _apply_artifact(
        {"id": "patch", "command_ref": "apply_patch"},
        {"patch": {"path": str(sdir / "artifacts" / "patch.json")}},
        sdir, root, None,
    )
    assert result is not None and result["applied"] is True, result
    assert "fixed" in (root / "sizes.py").read_text(encoding="utf-8")


def test_run_attempt_artifact_applied_before_checks(
    tmp_path: Path, apply_patch_cmd
) -> None:
    root = _git_repo(tmp_path)
    _, diff = _make_patch(root)
    sdir = _session_with_patch(root, diff)

    result = run_attempt(
        session_path=sdir / "session.jsonl",
        session_dir=sdir,
        workflow=_workflow(),
        evaluator_cmd=["true"],
        project_root=root,
        machine_home=None,
    )
    # the check ran (no evaluator criteria), patch applied before it
    assert "fixed" in (root / "sizes.py").read_text(encoding="utf-8")


def test_inapplicable_patch_fails_check(tmp_path: Path, apply_patch_cmd) -> None:
    root = _git_repo(tmp_path)
    bad_diff = (
        "diff --git a/other.py b/other.py\n"
        "--- a/other.py\n+++ b/other.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-x\n+y\n"
    )
    sdir = _session_with_patch(root, bad_diff)
    result = _apply_artifact(
        {"id": "patch", "command_ref": "apply_patch"},
        {"patch": {"path": str(sdir / "artifacts" / "patch.json")}},
        sdir, root, None,
    )
    assert result is not None and result["applied"] is False
    assert "apply" in result["detail"] or "index" in result["detail"] or \
        "error" in result["detail"]