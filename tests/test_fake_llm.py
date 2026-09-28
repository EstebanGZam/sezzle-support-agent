"""FakeLLM: default responder, deterministic script replay, error injection per kind."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from support_agent.config import ConfigError, Settings
from support_agent.llm import (
    DEFAULT_FAKE_ANSWER,
    ERROR_CLASSES,
    RETRY_TABLE,
    AuthBillingError,
    FakeLLM,
    FakeScriptExhausted,
    FinalAnswer,
    LLMRequest,
    ProviderError,
    UserMessage,
    final_answer_json_schema,
    make_llm_client,
)

FINAL = {
    "answer": "Synthetic reply.",
    "escalation_reason": "none",
    "policy_applied": True,
    "cited_policies": ["POL-02"],
}


def request(tool_mode: str = "auto") -> LLMRequest:
    return LLMRequest(system="sys", contents=(UserMessage("q"),), tool_mode=tool_mode)


def fake_settings(**overrides: Any) -> Settings:
    return Settings(provider="fake", **overrides)


# --- default responder -------------------------------------------------------------------------


def test_default_responder_answers_every_call_directly() -> None:
    llm = FakeLLM()
    for _ in range(3):
        resp = llm.generate(request())
        assert resp.final_json == dict(DEFAULT_FAKE_ANSWER)
        assert resp.function_calls == () and not resp.malformed
        FinalAnswer.model_validate(resp.final_json)
    assert resp.final_json is not DEFAULT_FAKE_ANSWER  # fresh copy per call
    assert len(llm.requests) == 3


def test_default_answer_matches_architecture_spec() -> None:
    assert dict(DEFAULT_FAKE_ANSWER) == {
        "answer": "[fake] offline answer",
        "escalation_reason": "none",
        "policy_applied": False,
        "cited_policies": [],
    }


def test_make_llm_client_fake_without_script_uses_default_responder() -> None:
    llm = make_llm_client(fake_settings())
    assert isinstance(llm, FakeLLM)
    resp = llm.generate(request())
    assert resp.final_json == dict(DEFAULT_FAKE_ANSWER)
    assert resp.model_id == "fake:gemini-3.5-flash-lite"


# --- scripted replay ---------------------------------------------------------------------------

SCRIPT = [
    {"function_call": {"name": "get_my_orders", "args": {"order_id": "ord_1"}}},
    {"final": FINAL, "usage": {"input": 10, "output": 5, "cached": 4}},
    {"text": "not json"},
    {"function_calls": [{"name": "get_my_orders"}, {"name": "other_tool", "args": {"x": 1}}]},
]


def _replay(llm: FakeLLM) -> list[tuple]:
    out = []
    for _ in SCRIPT:
        r = llm.generate(request())
        out.append(
            (
                [(c.name, c.args, c.call_id) for c in r.function_calls],
                r.final_json,
                r.text,
                r.malformed,
                r.usage.to_dict(),
            )
        )
    return out


def test_script_replays_in_order_and_deterministically() -> None:
    first = _replay(FakeLLM(SCRIPT))
    assert first == _replay(FakeLLM(SCRIPT))
    calls, final, _, malformed, _ = first[0]
    assert calls == [("get_my_orders", {"order_id": "ord_1"}, "fake_call_0_0")]
    assert final is None and not malformed
    assert first[1][1] == FINAL
    assert first[1][4] == {"input": 10, "output": 5, "cached": 4, "thoughts": 0}
    assert first[2][2] == "not json" and first[2][3] is True  # malformed → agent repairs
    assert [c[0] for c in first[3][0]] == ["get_my_orders", "other_tool"]


def test_raw_model_turn_is_opaque_and_step_scoped() -> None:
    llm = FakeLLM(SCRIPT[:2])
    a = llm.generate(request())
    b = llm.generate(request())
    assert a.raw_model_turn["fake_step"] == 0 and b.raw_model_turn["fake_step"] == 1


def test_requests_are_recorded_for_assertions() -> None:
    llm = FakeLLM([{"function_call": {"name": "get_my_orders"}}, {"final": FINAL}])
    llm.generate(request("auto"))
    llm.generate(request("none"))
    assert [r.tool_mode for r in llm.requests] == ["auto", "none"]


def test_exhausted_script_raises_or_switches_to_default() -> None:
    strict = FakeLLM([{"final": FINAL}])
    strict.generate(request())
    with pytest.raises(FakeScriptExhausted):
        strict.generate(request())

    lenient = FakeLLM([{"final": FINAL}], on_exhausted="default")
    assert lenient.generate(request()).final_json == FINAL
    assert lenient.generate(request()).final_json == dict(DEFAULT_FAKE_ANSWER)


def test_fake_llm_script_file_replay(tmp_path: Path) -> None:
    path = tmp_path / "script.json"
    path.write_text(json.dumps(SCRIPT), encoding="utf-8")
    settings = Settings.from_env({"LLM_PROVIDER": "fake", "FAKE_LLM_SCRIPT": str(path)})
    assert _replay(make_llm_client(settings)) == _replay(FakeLLM(SCRIPT))


def test_fake_llm_script_object_form(tmp_path: Path) -> None:
    path = tmp_path / "script.json"
    path.write_text(json.dumps({"steps": [{"final": FINAL}], "on_exhausted": "default"}))
    llm = FakeLLM.from_settings(fake_settings(fake_llm_script=path))
    assert llm.generate(request()).final_json == FINAL
    assert llm.generate(request()).final_json == dict(DEFAULT_FAKE_ANSWER)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"steps": "nope"}),
        json.dumps({"steps": [], "on_exhausted": "maybe"}),
        json.dumps([{"final": FINAL, "text": "both"}]),
        json.dumps([{"answer": "missing kind"}]),
        json.dumps([{"error": "not_a_kind"}]),
        json.dumps([{"function_call": {"args": {}}}]),
        json.dumps([{"final": FINAL, "usage": {"tokens": 1}}]),
    ],
)
def test_invalid_script_file_is_a_config_error(tmp_path: Path, content: str) -> None:
    path = tmp_path / "script.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError):
        FakeLLM.from_settings(fake_settings(fake_llm_script=path))


def test_missing_script_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        FakeLLM.from_settings(fake_settings(fake_llm_script=tmp_path / "absent.json"))


# --- error injection per kind (same §7 engine as the Gemini adapter) ----------------------------


@pytest.mark.parametrize("kind", ERROR_CLASSES)
def test_error_injection_per_kind_single_model(kind: str) -> None:
    llm = FakeLLM([{"error": kind}, {"error": kind}, {"final": FINAL}])
    with pytest.raises(ProviderError) as info:
        llm.generate(request())
    err = info.value
    assert err.kind == kind
    assert isinstance(err, AuthBillingError) == (kind == "auth_billing")
    rule = RETRY_TABLE[kind]
    expected = ["fake-primary", "fake-primary"] if rule.same_model_retry else ["fake-primary"]
    assert llm.attempt_models == expected
    assert [a.error_class for a in err.attempts] == [kind] * len(expected)
    assert err.attempts[-1].status == "failed"


@pytest.mark.parametrize("kind", ERROR_CLASSES)
def test_error_injection_per_kind_with_fallback(kind: str) -> None:
    llm = FakeLLM([{"error": kind}, {"final": FINAL}], fallback_model="fake-fallback")
    rule = RETRY_TABLE[kind]
    if not (rule.same_model_retry or rule.fallback_eligible):
        with pytest.raises(ProviderError):
            llm.generate(request())
        assert llm.attempt_models == ["fake-primary"]
        return
    resp = llm.generate(request())
    second = "fake-fallback" if rule.fallback_eligible else "fake-primary"
    assert llm.attempt_models == ["fake-primary", second]
    assert resp.model_id == second and resp.final_json == FINAL
    assert resp.fallback_used is (second == "fake-fallback")


def test_fake_quota_daily_disables_primary_for_the_batch() -> None:
    llm = FakeLLM(
        [{"error": "quota_daily"}, {"final": FINAL}, {"final": FINAL}],
        fallback_model="fake-fallback",
    )
    llm.generate(request())
    llm.generate(request())
    assert llm.attempt_models == ["fake-primary", "fake-fallback", "fake-fallback"]


def test_fake_auth_billing_latches_without_more_attempts() -> None:
    llm = FakeLLM([{"error": "auth_billing"}, {"final": FINAL}], fallback_model="fake-fallback")
    with pytest.raises(AuthBillingError):
        llm.generate(request())
    with pytest.raises(AuthBillingError):
        llm.generate(request())
    assert llm.attempt_models == ["fake-primary"]
    assert llm.remaining_steps == 1


def test_from_settings_mirrors_models_and_attempt_budget() -> None:
    llm = FakeLLM.from_settings(fake_settings(max_attempts=3))
    assert llm.runner.models == ("fake:gemini-3.5-flash-lite", "fake:gemini-3.1-flash-lite")
    assert llm.runner.max_attempts == 3


# --- final answer schema ---------------------------------------------------------------------


def test_final_answer_schema_is_canonical() -> None:
    schema = final_answer_json_schema()
    assert schema["required"] == ["answer", "escalation_reason", "policy_applied", "cited_policies"]
    assert schema["properties"]["escalation_reason"]["enum"][0] == "none"
    assert schema["properties"]["answer"]["maxLength"] == 1200


@pytest.mark.parametrize(
    "bad",
    [
        {**FINAL, "escalation_reason": None},
        {**FINAL, "escalation_reason": "whatever"},
        {**FINAL, "policy_applied": "true"},
        {**FINAL, "answer": "x" * 1201},
        {**FINAL, "route": "policy"},
        {k: v for k, v in FINAL.items() if k != "cited_policies"},
    ],
)
def test_final_answer_rejects_invalid(bad: dict) -> None:
    with pytest.raises(ValueError):
        FinalAnswer.model_validate(bad)
