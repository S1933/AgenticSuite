"""Lot 2 demonstration — ADR 0005 validation #2.

The same workflow resolves actor and evaluator onto two DISTINCT
providers (a model for the actor, a CLI for the evaluator), and the
project's command_refs (run_tests, run_lint) resolve through
.agentic/commands.yaml. No provider or model name appears in the
workflow itself (validation #3).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_suite.commands import resolve_command_ref
from agentic_suite.providers import (
    ProviderCapabilityError,
    resolve_role_provider,
)

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_machine_config() -> dict:
    """Read the repo reference config as if it were the machine config."""
    base = REPO_ROOT / "config"
    providers = yaml.safe_load((base / "providers.yaml").read_text(encoding="utf-8"))
    assignments = yaml.safe_load(
        (base / "role_assignments.yaml").read_text(encoding="utf-8")
    )
    return {
        "providers": providers["providers"],
        "assignments": assignments["role_assignments"],
    }


def test_actor_and_evaluator_resolve_to_two_distinct_providers() -> None:
    cfg = _load_machine_config()
    assignments = cfg["assignments"]
    actor_id = assignments["actor"]
    evaluator_id = assignments["evaluator"]
    assert actor_id != evaluator_id, "actors and evaluators must use distinct providers"

    kinds = {p["id"]: p["kind"] for p in cfg["providers"]}
    assert kinds[actor_id] == "model"
    assert kinds[evaluator_id] == "cli"


def test_actor_cannot_be_served_by_readonly_cli(tmp_path_factory) -> None:
    """A cli provider that lacks code_editing cannot serve actor (D3)."""
    evaluator_cli = {
        "id": "evaluator_cli",
        "kind": "cli",
        "capabilities": ["reasoning", "read_only"],
        "config": {},
    }
    home = tmp_path_factory.mktemp("home")
    base = home / ".config" / "agentic"
    base.mkdir(parents=True)
    (base / "providers.yaml").write_text(
        yaml.safe_dump({"providers": [evaluator_cli]}), encoding="utf-8"
    )
    (base / "role_assignments.yaml").write_text(
        yaml.safe_dump({"role_assignments": {"actor": "evaluator_cli",
                                             "evaluator": "evaluator_cli"}}),
        encoding="utf-8",
    )
    with pytest.raises(ProviderCapabilityError):
        resolve_role_provider("actor", config_home=home)


def test_project_command_refs_resolve_from_repo() -> None:
    """run_tests and run_lint resolve through the repo's .agentic/commands.yaml."""
    for ref in ("run_tests", "run_lint"):
        resolved = resolve_command_ref(REPO_ROOT, ref, machine_home=None)
        assert resolved is not None, f"{ref} must resolve"
        assert isinstance(resolved["argv"], list)
        assert resolved["argv"][0]
        assert resolved["timeout_seconds"] > 0


def test_workflow_contains_no_vendor_names() -> None:
    """ADR 0005 validation #3: no provider/model name inside workflows/."""
    workflow = (REPO_ROOT / "workflows" / "v1" / "bugfix.yaml").read_text(encoding="utf-8")
    for vendor in ("opencode", "anthropic", "openai", "claude", "deepseek", "gpt"):
        assert vendor not in workflow.lower(), f"workflow must stay vendor-free: {vendor}"