"""Model actor adapter — parsing, retry, contract building (Lot 5).

CI rule: _call_llm is mocked; no real model is ever called by tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_suite.providers import model_actor as actor
from agentic_suite.providers.model_evaluator import _machine_config, _api_key

pytestmark = pytest.mark.verification


@pytest.fixture
def fake_machine_config(tmp_path_factory) -> Path:
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


def _state(**overrides) -> dict:
    state = {
        "id": "discovery",
        "description": "understand the bug",
        "context_fields": [
            {"id": "observed", "type": "text", "required": True,
             "description": "what happens"},
            {"id": "expected", "type": "text", "required": True,
             "description": "what should happen"},
            {"id": "impact_scope", "type": "enum", "vocabulary": "impact_scope",
             "required": False, "description": "who is affected"},
        ],
        "produces": [
            {"id": "notes", "kind": "note", "required": True,
             "description": "interview journal"},
        ],
    }
    state.update(overrides)
    return state


def test_act_returns_context_and_artifacts(monkeypatch, fake_machine_config) -> None:
    monkeypatch.setattr(
        actor, "_call_llm",
        lambda *a, **k: json.dumps({
            "context": {"observed": "app crashes", "expected": "app works",
                        "impact_scope": "all_users"},
            "artifacts": {"notes": "asked 3 questions"},
        }),
    )
    result = actor.act(_state(), {}, {}, config_home=fake_machine_config)
    assert result["context"]["observed"] == "app crashes"
    assert result["context"]["impact_scope"] == "all_users"
    assert result["artifacts"]["notes"]


def test_act_accepts_documented_unknown(monkeypatch, fake_machine_config) -> None:
    """A required field the actor cannot establish becomes a documented unknown."""
    monkeypatch.setattr(
        actor, "_call_llm",
        lambda *a, **k: json.dumps({
            "context": {"observed": "crash",
                        "expected": {"_unknown": True,
                                     "_reason": "no spec available"}},
            "artifacts": {"notes": "n/a"},
        }),
    )
    result = actor.act(_state(), {}, {}, config_home=fake_machine_config)
    expected = result["context"]["expected"]
    assert isinstance(expected, dict)
    assert expected["_unknown"] is True
    assert expected["_reason"]


def test_act_retries_on_malformed(monkeypatch, fake_machine_config) -> None:
    calls = {"n": 0}

    def _bad(*a, **k):
        calls["n"] += 1
        return "not json at all"

    monkeypatch.setattr(actor, "_call_llm", _bad)
    monkeypatch.setattr(actor, "time", type("T", (), {"sleep": staticmethod(lambda s: None)})())
    with pytest.raises(actor.ActorError):
        actor.act(_state(), {}, {}, config_home=fake_machine_config)
    assert calls["n"] == actor._RETRIES + 1


def test_build_state_contract_lists_fields_and_artifacts() -> None:
    contract = actor._build_state_contract(_state())
    assert "observed [text, required] what happens" in contract
    assert "impact_scope [enum, optional (vocab: impact_scope)]" in contract
    assert "notes (kind: note, required) interview journal" in contract
    assert "description: understanding the bug" not in contract  # short desc used


def test_parse_output_accepts_code_fence() -> None:
    raw = "```json\n" + json.dumps({"context": {"a": "b"}, "artifacts": {}}) + "\n```"
    result = actor._parse_output(raw)
    assert result["context"]["a"] == "b"


def test_parse_output_rejects_bad_shapes() -> None:
    with pytest.raises(actor.ActorError):
        actor._parse_output("[]")            # not an object
    with pytest.raises(actor.ActorError):
        actor._parse_output('{"context": []}')  # context not a dict
    with pytest.raises(actor.ActorError):
        actor._parse_output("plain text")