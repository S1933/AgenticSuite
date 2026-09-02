"""Lint errors and warnings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LintMessage:
    """A lint finding: error or warning at a specific path in the workflow."""

    rule_id: str  # e.g. "R4" or "ADR-0003-D4"
    severity: str  # "error" | "warning"
    path: str  # dotted path in the workflow, e.g. "states.discovery.checks[0].command_ref"
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule_id} at {self.path}: {self.message}"


class LintError(Exception):
    """Raised by lint rules that fail with a fatal error."""


# Convenience constructors for readability in rule code.
def error(rule_id: str, path: str, message: str) -> LintMessage:
    return LintMessage(rule_id=rule_id, severity="error", path=path, message=message)


def warning(rule_id: str, path: str, message: str) -> LintMessage:
    return LintMessage(
        rule_id=rule_id, severity="warning", path=path, message=message
    )