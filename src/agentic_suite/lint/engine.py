"""Lint engine: runs all registered rules and accumulates messages."""

from __future__ import annotations

from collections.abc import Iterable

from agentic_suite.lint import LintMessage
from agentic_suite.lint.rules import ALL_RULES


def lint(workflow: dict) -> list[LintMessage]:
    """Run all lint rules against a workflow dict.

    Returns the list of lint messages in rule-order. Returns an empty
    list if the workflow passes cleanly.
    """
    messages: list[LintMessage] = []
    for rule in ALL_RULES:
        messages.extend(rule(workflow))
    return messages


def has_errors(messages: Iterable[LintMessage]) -> bool:
    """Return True if any message has severity=error."""
    return any(m.severity == "error" for m in messages)