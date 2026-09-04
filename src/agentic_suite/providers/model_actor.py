"""Model actor adapter — the worker (ADR 0003 D9 counterpart).

Invoked as a separate process with a fresh context: argv[-1] is the
journal copy, the state contract arrives on stdin. The actor produces
work — context fields and artifacts — that the evaluator later judges.
It never writes the session itself (ADR 0006 D2 spirit): it returns
content, the runner persists it through the chain.

Tests mock _call_llm; CI never calls a real model.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from agentic_suite.providers.model_evaluator import _machine_config, _call_llm

PROMPT = """You are the WORKER (actor) of a declarative engineering workflow.

You receive the current state's contract, the context already collected,
and a read-only view of the project files to investigate.

Return a strict JSON object:
{{
  "context": {{ "<field_id>": <value> }},
  "artifacts": {{ "<artifact_id>": <content> }}
}}

Rules:
- Fill every REQUIRED context field declared by the state. If you cannot
  establish a required field, set it to {{"_unknown": true, "_reason": "..."}}
  with a non-empty reason (documented unknown, ADR 0003 D1).
- Optional fields: fill only when you have real information.
- Produce every REQUIRED artifact declared by the state (kind noted in the
  contract). Content is the actual work product (text, JSON, diff...).
- enum fields: value must be one of the vocabulary values.
- list fields: JSON array. text fields: string.
- No prose outside the JSON object.

PROJECT FILES (read-only, use them for investigation and patch work):
{project_files}

STATE CONTRACT:
{state}

CONTEXT ALREADY COLLECTED:
{context}

WORKFLOW CONTEXT (other collected fields, read-only):
{workflow_context}
"""


def _project_files_snippet(project_root: Path, max_bytes: int = 60000) -> str:
    """A read-only snapshot of the project tree for the actor.

    Includes relative paths + contents of the code files (bounded). The
    session dir and .git are excluded.
    """
    if project_root is None or not project_root.is_dir():
        return "(no project directory provided)"
    skip = {"sessions", ".git", "__pycache__", ".venv", "node_modules"}
    lines = []
    budget = max_bytes
    for path in sorted(project_root.rglob("*")):
        rel = path.relative_to(project_root)
        if any(part in skip for part in rel.parts):
            continue
        if path.is_file():
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > 20000:
                lines.append(f"{rel}  (file, {size} bytes, not shown)")
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            lines.append(f"=== {rel} ===")
            lines.append(content[:8000])
            budget -= size
            if budget <= 0:
                lines.append("...(snapshot truncated by size budget)")
                break
    return "\n".join(lines) or "(empty project)"

_RETRIES = 2


class ActorError(RuntimeError):
    """The actor failed after retries on malformed output."""


def _build_state_contract(state: dict) -> str:
    """A human-readable contract for the actor (fields, vocab, artifacts)."""
    lines = [f"id: {state.get('id')}"]
    if state.get("description"):
        lines.append(f"description: {state.get('description')}")
    fields = []
    for cf in state.get("context_fields") or []:
        required = "required" if cf.get("required") else "optional"
        vocab = f" (vocab: {cf.get('vocabulary')})" if cf.get("vocabulary") else ""
        fields.append(f"- {cf.get('id')} [{cf.get('type')}, {required}{vocab}] "
                      f"{cf.get('description', '')}")
    if fields:
        lines.append("context_fields:")
        lines.extend(fields)
    artifacts = []
    for pr in state.get("produces") or []:
        required = "required" if pr.get("required") else "optional"
        artifacts.append(f"- {pr.get('id')} (kind: {pr.get('kind')}, {required}) "
                         f"{pr.get('description', '')}")
    if artifacts:
        lines.append("produces:")
        lines.extend(artifacts)
    return "\n".join(lines)


def _build_prompt(state: dict, context: dict, workflow_context: dict,
                  project_root: Path | None = None) -> str:
    return PROMPT.format(
        state=_build_state_contract(state),
        context=json.dumps(context, ensure_ascii=False, indent=2),
        workflow_context=json.dumps(workflow_context, ensure_ascii=False, indent=2),
        project_files=_project_files_snippet(project_root) if project_root else "(no project directory provided)",
    )


def _parse_output(raw: str) -> dict:
    """Parse the actor's JSON. Raises ActorError on malformed output."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ActorError("no JSON object in actor output")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ActorError(f"malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ActorError("actor output is not an object")
    context = data.get("context")
    artifacts = data.get("artifacts")
    if context is None:
        context = {}
    if artifacts is None:
        artifacts = {}
    if not isinstance(context, dict) or not isinstance(artifacts, dict):
        raise ActorError("context/artifacts must be JSON objects")
    return {"context": context, "artifacts": artifacts}


def act(
    state: dict,
    context: dict,
    workflow_context: dict,
    config_home: Path | None = None,
    project_root: Path | None = None,
) -> dict:
    """Run the actor over the state contract; returns {context, artifacts}."""
    prompt = _build_prompt(state, context, workflow_context, project_root)
    config = _machine_config(config_home)
    cfg = config.get("config") or {}
    endpoint = cfg.get("endpoint", "https://opencode.ai/zen/go/v1/chat/completions")
    model = cfg.get("model", "deepseek-v4-flash")
    key = _api_key(config)

    last_error: Exception | None = None
    for _ in range(_RETRIES + 1):
        try:
            raw = _call_llm(endpoint, key, model, prompt)
            return _parse_output(raw)
        except (ActorError, RuntimeError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise ActorError(f"actor failed after {_RETRIES + 1} attempts: {last_error}")


def _api_key(config: dict) -> str:
    from agentic_suite.providers.model_evaluator import _api_key as _k

    return _k(config)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 1:
        print("usage: model_actor [--config-home <dir>] [--project-root <dir>] "
              "<session-journal-copy>", file=sys.stderr)
        return 2
    config_home: Path | None = None
    project_root: Path | None = None
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--config-home" and i + 1 < len(argv):
            config_home = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--project-root" and i + 1 < len(argv):
            project_root = Path(argv[i + 1])
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    try:
        payload = json.load(sys.stdin)
        state = payload.get("state")
        context = payload.get("context") or {}
        workflow_context = payload.get("workflow_context") or {}
        if not isinstance(state, dict):
            raise ValueError("payload.state must be an object")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: bad stdin payload: {exc}", file=sys.stderr)
        return 2
    try:
        result = act(state, context, workflow_context,
                     config_home=config_home, project_root=project_root)
    except ActorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())