"""command_ref resolution — ADR 0005 D5.

Hierarchy: project (.agentic/commands.yaml) wins over machine
(~/.config/agentic/commands.yaml). Definitions are argv lists — no shell,
no substitution. An unresolved ref yields None (the check fails at
runtime with command_ref_unresolved, never at read time).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_suite.commands import (
    CommandRefError,
    resolve_command_ref,
)

pytestmark = pytest.mark.refusal


def _write_project_commands(proj: Path, commands: dict) -> str:
    import yaml

    d = proj / ".agentic"
    d.mkdir(parents=True, exist_ok=True)
    (d / "commands.yaml").write_text(yaml.safe_dump(commands), encoding="utf-8")
    return str(d / "commands.yaml")


def _write_machine_commands(tmp_home: Path, commands: dict) -> str:
    import yaml

    base = tmp_home / ".config" / "agentic"
    base.mkdir(parents=True, exist_ok=True)
    p = base / "commands.yaml"
    p.write_text(yaml.safe_dump(commands), encoding="utf-8")
    return str(p)


def test_project_commands_resolved(tmp_path_factory, monkeypatch) -> None:
    """A ref defined in .agentic/commands.yaml resolves with argv."""
    proj = tmp_path_factory.mktemp("proj")
    _write_project_commands(proj, {
        "commands": {"run_tests": {"argv": ["pytest", "-q"], "timeout_seconds": 120}}
    })
    resolved = resolve_command_ref(proj, "run_tests", machine_home=None)
    assert resolved == {"argv": ["pytest", "-q"], "timeout_seconds": 120, "cwd": None}


def test_machine_commands_used_when_project_missing(tmp_path_factory) -> None:
    """Fallback to ~/.config/agentic/commands.yaml when project has no file."""
    proj = tmp_path_factory.mktemp("proj")
    home = tmp_path_factory.mktemp("home")
    _write_machine_commands(home, {
        "commands": {"run_lint": {"argv": ["ruff", "check", "."]}}
    })
    resolved = resolve_command_ref(proj, "run_lint", machine_home=home)
    assert resolved["argv"] == ["ruff", "check", "."]


def test_project_wins_over_machine(tmp_path_factory) -> None:
    """D5: project definition takes precedence over machine definition."""
    proj = tmp_path_factory.mktemp("proj")
    home = tmp_path_factory.mktemp("home")
    _write_project_commands(proj, {
        "commands": {"run_tests": {"argv": ["pytest", "-q", "--strict"]}}
    })
    _write_machine_commands(home, {
        "commands": {"run_tests": {"argv": ["pytest"]}}
    })
    resolved = resolve_command_ref(proj, "run_tests", machine_home=home)
    assert resolved["argv"] == ["pytest", "-q", "--strict"]


def test_unknown_ref_returns_none(tmp_path_factory) -> None:
    """Unresolved ref -> None; the check fails at runtime, not at read time."""
    proj = tmp_path_factory.mktemp("proj")
    home = tmp_path_factory.mktemp("home")
    _write_machine_commands(home, {
        "commands": {"run_tests": {"argv": ["pytest"]}}
    })
    assert resolve_command_ref(proj, "run_nothing", machine_home=home) is None


def test_full_argv_required(tmp_path_factory) -> None:
    """D5: argv is mandatory; shell-string form is refused."""
    proj = tmp_path_factory.mktemp("proj")
    _write_project_commands(proj, {
        "commands": {"run_tests": {"cmd": "pytest -q"}}  # wrong key, shell-ish
    })
    with pytest.raises(CommandRefError):
        resolve_command_ref(proj, "run_tests", machine_home=None)


def test_argv_must_be_list(tmp_path_factory) -> None:
    """D5: argv must be a list of strings; a plain string is refused."""
    proj = tmp_path_factory.mktemp("proj")
    _write_project_commands(proj, {
        "commands": {"run_tests": {"argv": "pytest -q"}}
    })
    with pytest.raises(CommandRefError):
        resolve_command_ref(proj, "run_tests", machine_home=None)


def test_no_shell_substitution(tmp_path_factory) -> None:
    """D5: no templates, no env substitution — the argv list is used as-is."""
    proj = tmp_path_factory.mktemp("proj")
    _write_project_commands(proj, {
        "commands": {"run_tests": {"argv": ["$PWD", "{{suite}}"]}}
    })
    resolved = resolve_command_ref(proj, "run_tests", machine_home=None)
    # Literal, untouched tokens.
    assert resolved["argv"] == ["$PWD", "{{suite}}"]