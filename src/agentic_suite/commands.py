"""command_ref resolution — ADR 0005 D5.

Hierarchy: project (``<projet>/.agentic/commands.yaml``) wins over machine
(``~/.config/agentic/commands.yaml``). Definitions are argv lists — no
shell, no template, no substitution. An unresolved ref yields ``None`` so
the check fails at runtime with ``command_ref_unresolved``, never at read
time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

# Directory where the machine-level commands.yaml lives.
MACHINE_CONFIG_DIR_NAME = ".config/agentic"
# Project-level commands file, relative to the project root.
PROJECT_COMMANDS_REL = ".agentic/commands.yaml"

# Default timeout for a resolved command, in seconds (ADR 0005 D5).
DEFAULT_TIMEOUT_SECONDS = 60


class CommandRefError(Exception):
    """Raised when a commands.yaml definition is malformed (D5)."""


def _load_commands_file(path: Path) -> Optional[dict]:
    """Return the ``commands:`` mapping of *path*, or None if absent/empty."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return None
    if not isinstance(raw, dict):
        raise CommandRefError(f"{path}: root must be a mapping")
    commands = raw.get("commands")
    if commands is None:
        raise CommandRefError(f"{path}: missing 'commands:' section")
    if not isinstance(commands, dict):
        raise CommandRefError(f"{path}: 'commands:' must be a mapping")
    return commands


def _normalize_definition(path: Path, ref: str, definition: Any) -> dict:
    """Validate a single command definition (D5: argv required, list, no shell)."""
    if not isinstance(definition, dict):
        raise CommandRefError(f"{path}: commands.{ref} must be a mapping")
    argv = definition.get("argv")
    if not isinstance(argv, list) or not argv:
        raise CommandRefError(
            f"{path}: commands.{ref} requires a non-empty 'argv' list"
        )
    if not all(isinstance(a, str) for a in argv):
        raise CommandRefError(
            f"{path}: commands.{ref}.argv must be a list of strings"
        )
    # The argv list is used as-is: $VAR and {{tpl}} tokens are literal,
    # never substituted (D5: no expressions, no templates).
    timeout = definition.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, int) or timeout <= 0:
        raise CommandRefError(
            f"{path}: commands.{ref}.timeout_seconds must be a positive int"
        )
    cwd = definition.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd):
        raise CommandRefError(
            f"{path}: commands.{ref}.cwd must be a relative path string"
        )
    return {"argv": list(argv), "timeout_seconds": timeout, "cwd": cwd}


def _project_commands_file(project_root: Path) -> Path:
    return project_root / PROJECT_COMMANDS_REL


def _machine_commands_file(machine_home: Optional[Path]) -> Optional[Path]:
    if machine_home is None:
        return None
    return machine_home / MACHINE_CONFIG_DIR_NAME / "commands.yaml"


def resolve_command_ref(
    project_root: Path,
    ref: str,
    machine_home: Optional[Path] = None,
) -> Optional[dict]:
    """Resolve *ref* to a command definition, project level first (D5).

    Returns a dict with keys ``argv``, ``timeout_seconds``, ``cwd``, or
    ``None`` when the ref is defined nowhere. Raises :class:`CommandRefError`
    when a definition is present but malformed.
    """
    # Project wins over machine (D5).
    project_file = _project_commands_file(project_root)
    try:
        project_commands = _load_commands_file(project_file)
    except CommandRefError:
        raise
    if project_commands is not None and ref in project_commands:
        return _normalize_definition(project_file, ref, project_commands[ref])

    machine_file = _machine_commands_file(machine_home)
    if machine_file is not None:
        machine_commands = _load_commands_file(machine_file)
        if machine_commands is not None and ref in machine_commands:
            return _normalize_definition(machine_file, ref, machine_commands[ref])

    return None