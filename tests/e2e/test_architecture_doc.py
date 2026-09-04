"""P1 — architecture.md must describe one territory (Lot F).

Two contracts, both enforced by reading the docs themselves:

1. Every module documented in architecture.md §2 (the "present" list)
   must import cleanly.
2. Every module documented in architecture.md §4 (the "absent" list)
   must raise ImportError — if an "absent" module imports, the doc is
   stale and the test fails. Same for CLI subcommands: those documented
   in reference/cli.md must exist in the real parser and vice versa.
"""

from __future__ import annotations

import argparse
import importlib
import re
from pathlib import Path

import pytest

from agentic_suite.cli import _build_parser

pytestmark = pytest.mark.e2e

REPO = Path(__file__).resolve().parent.parent.parent
ARCH = REPO / "docs" / "architecture.md"
CLI_DOC = REPO / "docs" / "reference" / "cli.md"

# Modules that must exist (architecture.md §2 "### `...`" headings).
# §2 documents packages and modules; the import contract applies to
# Python modules only (files), not package directories.
PRESENT = [
    "agentic_suite",
    "agentic_suite.loader",
    "agentic_suite.lint",
    "agentic_suite.lint.engine",
    "agentic_suite.lint.rules",
    "agentic_suite.verification.checks",
    "agentic_suite.session",
    "agentic_suite.evaluator",
    "agentic_suite.commands",
    "agentic_suite.providers",
    "agentic_suite.providers.base",
    "agentic_suite.providers.model_evaluator",
    "agentic_suite.providers.model_actor",
    "agentic_suite.skills",
    "agentic_suite.engine",
    "agentic_suite.runner",
    "agentic_suite.session_loop",
    "agentic_suite.cli",
]


def _absent_modules() -> list[str]:
    """Modules explicitly declared absent by architecture.md §4.

    Scans the "Absent" column of the §4 table for ``agentic_suite.X``
    references. Each must fail to import.
    """
    text = ARCH.read_text(encoding="utf-8")
    section = text.split("## 4. ")[1].split("## 5. ")[0]
    found = set()
    for match in re.finditer(r"`(agentic_suite[\w./]+)`", section):
        name = match.group(1)
        # file-like paths map to the module name (src layout)
        found.add(name.replace("/", "."))
    return sorted(found)


def _documented_subcommands() -> set[str]:
    text = CLI_DOC.read_text(encoding="utf-8")
    return {
        m.group(1)
        for m in re.finditer(r"^## `agentic (\w+)", text, flags=re.MULTILINE)
    }


def _real_subcommands() -> set[str]:
    parser = _build_parser()
    sub_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    return set(sub_action.choices)


@pytest.mark.parametrize("module_name", PRESENT)
def test_present_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)


def test_documented_absent_modules_are_really_absent() -> None:
    absent = _absent_modules()
    assert absent, "architecture.md §4 declares no absent modules — doc regression?"
    for module_name in absent:
        with pytest.raises(ImportError):
            importlib.import_module(module_name)


def test_cli_doc_matches_real_subcommands() -> None:
    documented = _documented_subcommands()
    real = _real_subcommands()
    assert documented == real, (
        f"CLI subcommands drift: documented={sorted(documented)} "
        f"real={sorted(real)}"
    )