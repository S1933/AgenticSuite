"""YAML loader for workflow definitions.

Loads a workflow YAML file into a Python dict. Errors at this level are
load errors (file not found, malformed YAML, root not a mapping), not
schema errors. Schema errors are reported by the linter.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class LoadError(Exception):
    """Raised when a workflow YAML cannot be loaded."""


def load_workflow(path: str | Path) -> dict:
    """Load a workflow YAML file and return its parsed content.

    Args:
        path: Path to the workflow YAML file.

    Returns:
        The parsed workflow as a dict.

    Raises:
        LoadError: If the file cannot be read, the YAML is malformed,
            or the root is not a mapping.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise LoadError(f"cannot read workflow file '{p}': {e}") from e

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise LoadError(f"malformed YAML in '{p}': {e}") from e

    if not isinstance(data, dict):
        raise LoadError(
            f"workflow root must be a mapping, got {type(data).__name__}"
        )

    return data