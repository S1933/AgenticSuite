"""Model evaluator adapter — parsing, retry, never a real model in CI.

The CI rule (README testing strategy) applies: these tests mock
_call_llm/_parse_verdicts so no network request ever reaches a provider.
The real adapter is exercised manually (smoke test documented in the
plan, Lot 4 discoveries).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_suite.providers import model_evaluator as me

pytestmark = pytest.mark.verification


@pytest.fixture
def fake_machine_config(tmp_path_factory) -> Path:
    """A minimal machine config with a key file (LLM call mocked anyway)."""
    import yaml

    home = tmp_path_factory.mktemp("home")
    cfg_dir = home / ".config" / "agentic"
    cfg_dir.mkdir(parents=True)
    key_file = cfg_dir / "key"
    key_file.write_text("sk-test", encoding="utf-8")
    (cfg_dir / "providers.yaml").write_text(yaml.safe_dump({"providers": [
        {"id": "opencode_model", "kind": "model", "capabilities": ["reasoning"],
         "config": {"endpoint": "https://mock", "model": "m",
                    "api_key_file": str(key_file)}}
    ]}), encoding="utf-8")
    return home


def _journal(tmp_path_factory) -> Path:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from agentic_suite.session import new_session

    jp = tmp_path_factory.mktemp("sess") / "session.jsonl"
    new_session(jp, to_state="discovery", workflow_version=1)
    return jp


def test_parse_verdicts_plain_json(monkeypatch, tmp_path_factory, fake_machine_config) -> None:
    jp = _journal(tmp_path_factory)
    monkeypatch.setattr(
        me, "_call_llm",
        lambda *a, **k: json.dumps({
            "verdicts": {
                "c1": {"verdict": "pass", "evidence": "artifacts.diagnosis"},
                "c2": {"verdict": "insufficient_evidence", "evidence": "context.x"},
            }
        }),
    )
    result = me.evaluate(jp, [{"id": "c1"}, {"id": "c2"}],
                         config_home=fake_machine_config)
    assert result["verdicts"]["c1"]["verdict"] == "pass"
    assert result["verdicts"]["c2"]["verdict"] == "insufficient_evidence"


def test_parse_verdicts_accepts_code_fence(monkeypatch, tmp_path_factory, fake_machine_config) -> None:
    jp = _journal(tmp_path_factory)
    monkeypatch.setattr(
        me, "_call_llm",
        lambda *a, **k: "```json\n" + json.dumps({
            "verdicts": {"c1": {"verdict": "fail", "evidence": "context.y"}}
        }) + "\n```",
    )
    result = me.evaluate(jp, [{"id": "c1"}], config_home=fake_machine_config)
    assert result["verdicts"]["c1"]["verdict"] == "fail"


def test_malformed_output_retries_then_hard_fails(monkeypatch, tmp_path_factory, fake_machine_config) -> None:
    """Malformed parse -> retry; never a guess; hard failure after N."""
    jp = _journal(tmp_path_factory)
    calls = {"n": 0}

    def _bad(*a, **k):
        calls["n"] += 1
        return "this is not json"

    monkeypatch.setattr(me, "_call_llm", _bad)
    monkeypatch.setattr(me, "time", type("T", (), {"sleep": staticmethod(lambda s: None)})())
    with pytest.raises(RuntimeError) as exc:
        me.evaluate(jp, [{"id": "c1"}], config_home=fake_machine_config)
    assert calls["n"] == me._RETRIES + 1
    assert "malformed" in str(exc.value).lower() or "json" in str(exc.value).lower()


def test_invalid_verdict_value_rejected(monkeypatch, tmp_path_factory, fake_machine_config) -> None:
    """A verdict outside pass|fail|insufficient_evidence is refused."""
    jp = _journal(tmp_path_factory)
    monkeypatch.setattr(
        me, "_call_llm",
        lambda *a, **k: json.dumps({"verdicts": {
            "c1": {"verdict": "maybe", "evidence": "context.x"}}}),
    )
    with pytest.raises(RuntimeError):
        me.evaluate(jp, [{"id": "c1"}], config_home=fake_machine_config)


def test_api_key_reads_from_key_file_not_env(tmp_path_factory) -> None:
    """The key comes from config.api_key_file; HOME-less env cannot starve it."""
    home = tmp_path_factory.mktemp("home")
    cfg_dir = home / ".config" / "agentic"
    cfg_dir.mkdir(parents=True)
    key_file = cfg_dir / "key"
    key_file.write_text("sk-secret", encoding="utf-8")
    import yaml

    (cfg_dir / "providers.yaml").write_text(yaml.safe_dump({"providers": [
        {"id": "opencode_model", "kind": "model", "capabilities": ["reasoning"],
         "config": {"endpoint": "https://x", "model": "m",
                    "api_key_file": str(key_file)}}
    ]}), encoding="utf-8")
    cfg = me._machine_config(config_home=home)
    assert me._api_key(cfg) == "sk-secret"