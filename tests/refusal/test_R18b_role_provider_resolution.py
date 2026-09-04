"""Role → provider resolution — ADR 0005 D1-D4.

Roles are closed (actor, evaluator); each role has implicit required
capabilities. Providers are declared in providers.yaml; role → provider
mapping lives in role_assignments.yaml at machine level and cannot be
overridden by a project. A provider may only serve a role whose required
capabilities are included in its provided capabilities.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_suite.providers import (
    RoleAssignmentMissing,
    ProviderCapabilityError,
    ProviderLoadError,
    resolve_role_provider,
)

pytestmark = pytest.mark.refusal

# ADR 0005 D2 — fixed per-role capability sets.
ACTOR_CAPS = {"reasoning", "code_editing", "tool_execution"}
EVALUATOR_CAPS = {"reasoning", "read_only"}


def _write_providers(home: Path, providers: list[dict]) -> None:
    base = home / ".config" / "agentic"
    base.mkdir(parents=True, exist_ok=True)
    (base / "providers.yaml").write_text(
        yaml.safe_dump({"providers": providers}), encoding="utf-8"
    )


def _write_assignments(home: Path, assignments: dict) -> None:
    base = home / ".config" / "agentic"
    base.mkdir(parents=True, exist_ok=True)
    (base / "role_assignments.yaml").write_text(
        yaml.safe_dump({"role_assignments": assignments}), encoding="utf-8"
    )


def _mock_model() -> dict:
    return {"id": "mock_model", "kind": "model",
            "capabilities": sorted(ACTOR_CAPS | {"read_only"})}


def _mock_cli() -> dict:
    return {"id": "mock_cli", "kind": "cli",
            "capabilities": ["reasoning", "read_only"]}


def test_actor_resolves_to_model_provider(tmp_path_factory) -> None:
    home = tmp_path_factory.mktemp("home")
    _write_providers(home, [_mock_model(), _mock_cli()])
    _write_assignments(home, {"actor": "mock_model", "evaluator": "mock_cli"})
    actor = resolve_role_provider("actor", config_home=home)
    evaluator = resolve_role_provider("evaluator", config_home=home)
    assert actor["id"] == "mock_model"
    assert actor["kind"] == "model"
    assert evaluator["id"] == "mock_cli"


def test_missing_assignment_raises(tmp_path_factory) -> None:
    home = tmp_path_factory.mktemp("home")
    _write_providers(home, [_mock_model()])
    _write_assignments(home, {"actor": "mock_model"})  # no evaluator
    with pytest.raises(RoleAssignmentMissing) as exc:
        resolve_role_provider("evaluator", config_home=home)
    assert "evaluator" in str(exc.value)


def test_missing_providers_file_raises(tmp_path_factory) -> None:
    home = tmp_path_factory.mktemp("home")
    _write_assignments(home, {"actor": "mock_model"})
    with pytest.raises(ProviderLoadError):
        resolve_role_provider("actor", config_home=home)


def test_assigned_provider_not_found_raises(tmp_path_factory) -> None:
    home = tmp_path_factory.mktemp("home")
    _write_providers(home, [_mock_cli()])
    _write_assignments(home, {"actor": "ghost", "evaluator": "mock_cli"})
    with pytest.raises(ProviderLoadError) as exc:
        resolve_role_provider("actor", config_home=home)
    assert "ghost" in str(exc.value)


def test_provider_missing_required_capability_rejected(tmp_path_factory) -> None:
    """actor requires code_editing + tool_execution; a read-only provider cannot serve it."""
    home = tmp_path_factory.mktemp("home")
    _write_providers(home, [_mock_cli()])  # only reasoning + read_only
    _write_assignments(home, {"actor": "mock_cli", "evaluator": "mock_cli"})
    with pytest.raises(ProviderCapabilityError) as exc:
        resolve_role_provider("actor", config_home=home)
    assert "code_editing" in str(exc.value)


def test_unknown_role_refused(tmp_path_factory) -> None:
    """D1: roles outside actor/evaluator are refused."""
    home = tmp_path_factory.mktemp("home")
    _write_providers(home, [_mock_model()])
    with pytest.raises(RoleAssignmentMissing) as exc:
        resolve_role_provider("reviewer", config_home=home)
    assert "reviewer" in str(exc.value)