"""Role → provider resolution — ADR 0005 D1-D4.

Roles are a closed set ({actor, evaluator}); each role has a fixed set of
implicit required capabilities (D2). Providers are declared in
``providers.yaml``; the role → provider mapping lives in
``role_assignments.yaml`` (machine level, not overridable by projects).
A provider may only serve a role whose required capabilities are a subset
of its provided capabilities (D3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

# ADR 0005 D1: the only existing roles.
ALLOWED_ROLES = frozenset({"actor", "evaluator"})

# ADR 0005 D2: fixed per-role capability sets.
ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    "actor": frozenset({"reasoning", "code_editing", "tool_execution"}),
    "evaluator": frozenset({"reasoning", "read_only"}),
}

# ADR 0005 D3: closed kind enum.
ALLOWED_KINDS = frozenset({"model", "cli", "api"})

# Machine config dir (mirrors commands.py MACHINE_CONFIG_DIR_NAME).
MACHINE_CONFIG_DIR_NAME = ".config/agentic"


class RoleAssignmentMissing(Exception):
    """role_assignments.yaml missing or does not declare a role (D4)."""


class ProviderLoadError(Exception):
    """providers.yaml unreadable, or the assigned provider id not listed."""


class ProviderCapabilityError(Exception):
    """The assigned provider lacks a capability the role requires (D3)."""


def _read_yaml(path: Path) -> Optional[dict]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return None
    return raw if isinstance(raw, dict) else None


def _load_assignments(config_home: Path) -> dict[str, str]:
    path = config_home / MACHINE_CONFIG_DIR_NAME / "role_assignments.yaml"
    raw = _read_yaml(path)
    if raw is None:
        return {}
    assignments = raw.get("role_assignments")
    if not isinstance(assignments, dict):
        return {}
    return {str(k): str(v) for k, v in assignments.items()}


def _load_providers(config_home: Path) -> dict[str, dict[str, Any]]:
    path = config_home / MACHINE_CONFIG_DIR_NAME / "providers.yaml"
    raw = _read_yaml(path)
    if raw is None:
        return {}
    providers = raw.get("providers")
    if not isinstance(providers, list):
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for entry in providers:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("id")
        if isinstance(pid, str) and pid:
            by_id[pid] = entry
    return by_id


def resolve_role_provider(role: str, config_home: Path) -> dict[str, Any]:
    """Resolve *role* to its provider (ADR 0005 D3/D4).

    Raises:
        RoleAssignmentMissing: role outside {actor, evaluator}, or not
            declared in role_assignments.yaml.
        ProviderLoadError: providers.yaml missing/empty, or the assigned
            provider id is not listed.
        ProviderCapabilityError: the provider does not cover the role's
            required capabilities.
    """
    if role not in ALLOWED_ROLES:
        raise RoleAssignmentMissing(
            f"role '{role}' is not in the closed set {sorted(ALLOWED_ROLES)}"
        )

    assignments_path = (
        config_home / MACHINE_CONFIG_DIR_NAME / "role_assignments.yaml"
    )
    if not assignments_path.exists():
        raise RoleAssignmentMissing(
            f"role_assignment_missing: {role} "
            f"({assignments_path} does not exist)"
        )
    assignments = _load_assignments(config_home)
    provider_id = assignments.get(role)
    if not provider_id:
        raise RoleAssignmentMissing(f"role_assignment_missing: {role}")

    providers = _load_providers(config_home)
    provider = providers.get(provider_id)
    if provider is None:
        raise ProviderLoadError(
            f"provider_load_error: {provider_id} (assigned to {role}) "
            f"not in providers.yaml"
        )

    kind = provider.get("kind")
    if kind not in ALLOWED_KINDS:
        raise ProviderLoadError(
            f"provider_load_error: {provider_id} has invalid kind {kind!r} "
            f"(allowed: {sorted(ALLOWED_KINDS)})"
        )

    provided = set(provider.get("capabilities") or [])
    required = ROLE_CAPABILITIES[role]
    missing = required - provided
    if missing:
        raise ProviderCapabilityError(
            f"provider {provider_id} cannot serve {role}: "
            f"missing capabilities {sorted(missing)}"
        )

    return provider