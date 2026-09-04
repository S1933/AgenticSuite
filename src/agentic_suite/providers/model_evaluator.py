"""Model evaluator adapter — the judge process (ADR 0003 D9).

Invoked as a separate process with a fresh context: argv[-1] is the
session journal copy (the ONLY thing pointing at the session), criteria
arrive on stdin. The judge never sees the worker's conversation.

Call pattern (wired via AGENTIC_EVALUATOR_CMD):
    python -m agentic_suite.providers.model_evaluator <session-copy> <criteria-stdin>

Reads its own machine config (provider + api key file) from
~/.config/agentic/ — not from the environment, so the isolation strip in
run_evaluator cannot starve it and secrets never ride env vars into
logger dumps.

Output (stdout): strict JSON matching run_evaluator's contract:
    {"verdicts": {"<criterion_id>": {"verdict": "pass|fail|insufficient_evidence",
                                     "evidence": "<artifact/context ref>"}}}
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROMPT = """You are the EVALUATOR of a declarative engineering workflow.

You receive ONLY the session record (journal) and the exit criteria. You
never saw the work conversation that produced the state — anything absent
from the session record is OUT OF SCOPE for you.

For each criterion, return a strict JSON object:
{{
  "verdicts": {{
    "<criterion_id>": {{
      "verdict": "pass" | "fail" | "insufficient_evidence",
      "evidence": "<exact reference from the session record>"
    }}
  }}
}}

Rules:
- "pass" only when the session record demonstrably satisfies the
  criterion. "insufficient_evidence" is a FAILURE: the burden is on the
  worker, not on you, to infer.
- "evidence" must cite an identifier that exists in the session record
  (context.<field>, artifacts.<id>, checks.<name>). Never invent one.
- No prose outside the JSON object.

SESSION RECORD (journal):
{journal}

CRITERIA TO JUDGE:
{criteria}
"""

_DEFAULT_ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
_DEFAULT_MODEL = "deepseek-v4-flash"
_RETRIES = 2  # hard failure after N malformed parses, never a guess


def _machine_config(config_home: Path | None = None) -> dict:
    """Read provider config from providers.yaml (ADR 0005).

    *config_home* is passed explicitly (the evaluator env strips HOME, so
    ~ cannot be resolved — argv survives the isolation strip).
    """
    base = (config_home or Path.home()) / ".config" / "agentic"
    providers_file = base / "providers.yaml"
    if not providers_file.is_file():
        return {}
    import yaml

    try:
        raw = yaml.safe_load(providers_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    for p in raw.get("providers") or []:
        if p.get("id") == "opencode_model" and p.get("kind") == "model":
            return p
    return {}


def _api_key(config: dict) -> str:
    """Read the API key from the configured key file (never an env var)."""
    key_file = (config.get("config") or {}).get("api_key_file")
    if not key_file:
        raise RuntimeError("opencode_model config.api_key_file not set")
    path = Path(key_file).expanduser()
    if not path.is_file():
        raise RuntimeError(f"api key file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def _call_llm(endpoint: str, key: str, model: str, prompt: str,
              timeout_s: float = 120.0) -> str:
    import httpx

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Cloudflare (1010) blocks default http clients — a real UA passes.
        "User-Agent": "agentic-suite/0.1 (python-httpx)",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2000,
    }
    resp = httpx.post(endpoint, json=payload, headers=headers, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"malformed LLM response: {data!r:.300}") from exc


def _parse_verdicts(raw: str) -> dict:
    """Parse the judge's JSON. Raises ValueError on malformed output."""
    # strip code fences if the model wrapped the JSON
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in judge output")
    data = json.loads(text[start : end + 1])
    verdicts = data.get("verdicts")
    if not isinstance(verdicts, dict):
        raise ValueError("judge output has no 'verdicts' object")
    return verdicts


def evaluate(
    journal_path: Path,
    criteria: list[dict],
    config_home: Path | None = None,
) -> dict:
    """Run the judge over the journal copy; returns {'verdicts': {...}}."""
    journal = journal_path.read_text(encoding="utf-8")
    criteria_text = json.dumps(criteria, ensure_ascii=False, indent=2)
    prompt = PROMPT.format(journal=journal, criteria=criteria_text)

    config = _machine_config(config_home)
    cfg = config.get("config") or {}
    endpoint = cfg.get("endpoint", _DEFAULT_ENDPOINT)
    model = cfg.get("model", _DEFAULT_MODEL)
    key = _api_key(config)

    last_error: Exception | None = None
    for _ in range(_RETRIES + 1):
        try:
            raw = _call_llm(endpoint, key, model, prompt)
            verdicts = _parse_verdicts(raw)
            # normalize: only known verdict values (never a guess)
            cleaned: dict[str, dict] = {}
            for cid, verdict in verdicts.items():
                if not isinstance(verdict, dict):
                    raise ValueError(f"verdict for {cid} is not an object")
                value = verdict.get("verdict")
                if value not in ("pass", "fail", "insufficient_evidence"):
                    raise ValueError(f"verdict for {cid} has invalid value {value!r}")
                cleaned[cid] = {"verdict": value,
                                "evidence": str(verdict.get("evidence", ""))}
            return {"verdicts": cleaned}
        except ValueError as exc:  # malformed parse -> retry
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"judge failed after {_RETRIES + 1} attempts: {last_error}")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 1:
        print("usage: model_evaluator [--config-home <dir>] <session-journal-copy>",
              file=sys.stderr)
        return 2
    config_home: Path | None = None
    rest: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--config-home" and i + 1 < len(argv):
            config_home = Path(argv[i + 1])
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    journal_path = Path(rest[-1])
    try:
        criteria = json.load(sys.stdin)
        if not isinstance(criteria, list):
            raise ValueError("criteria must be a JSON list")
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"error: bad criteria stdin: {exc}", file=sys.stderr)
        return 2
    try:
        result = evaluate(journal_path, criteria, config_home=config_home)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())