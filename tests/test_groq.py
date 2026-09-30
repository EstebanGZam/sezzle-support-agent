"""GroqCloud adapter: request shape, normalization, history, §7 errors, pacing (no network).

Every request goes through ``httpx.MockTransport``: a handler records the request and returns a
canned ``httpx.Response`` (or raises an ``httpx`` exception), so the real ``GroqClient`` code runs
end to end without any network access.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from support_agent.agent import AgentStatics, Case, answer_case
from support_agent.config import PROJECT_ROOT, ConfigError, Secret, Settings
from support_agent.llm import (
    AuthBillingError,
    FinalAnswer,
    LLMRequest,
    ModelTurn,
    ProviderError,
    ToolResult,
    UserMessage,
    make_llm_client,
)
from support_agent.llm.groq import (
    CHAT_COMPLETIONS_PATH,
    GROQ_BASE_URL,
    SUBMIT_ANSWER,
    GroqClient,
    TokenPacer,
    _request_chars,
    classify_response,
    to_messages,
    to_usage,
)
from support_agent.resources import Resources
from support_agent.tools import GET_MY_ORDERS_DECLARATION

PRIMARY = "openai/gpt-oss-120b"
FALLBACK = "openai/gpt-oss-20b"
KEY = "gsk_test-key-0123456789"
FINAL = {
    "answer": "Synthetic reply.",
    "escalation_reason": "none",
    "policy_applied": False,
    "cited_policies": [],
}
SYSTEM = "You are a support assistant for a fictional demo store."


# --- helpers ----------------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


Outcome = httpx.Response | BaseException | Callable[[httpx.Request], httpx.Response]


class Server:
    """A scripted Groq endpoint behind ``httpx.MockTransport``."""

    def __init__(self, outcomes: list[Outcome], clock: Clock | None = None) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[httpx.Request] = []
        self.clock = clock
        self.sent_at: list[float] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.clock is not None:
            self.sent_at.append(self.clock.t)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome) and not isinstance(outcome, httpx.Response):
            return outcome(request)
        return outcome

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]

    @property
    def models_called(self) -> list[str]:
        return [b["model"] for b in self.bodies]


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "provider": "groq",
        "primary_model": PRIMARY,
        "fallback_model": FALLBACK,
        "api_key": Secret(KEY),
        "max_attempts": 3,
        "timeout_s": 10.0,
        "max_output_tokens": 1024,
        "reasoning_effort": "low",
        "tpm_budget": 0,
        "min_call_interval_s": 0.0,
    }
    base.update(overrides)
    return Settings(**base)


def make_client(
    outcomes: list[Outcome], **overrides: Any
) -> tuple[GroqClient, Server, list[float], Clock]:
    clock = Clock()
    server = Server(outcomes, clock)
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.t += seconds

    client = GroqClient(
        settings(**overrides),
        transport=httpx.MockTransport(server.handler),
        sleep=sleep,
        clock=clock,
    )
    return client, server, sleeps, clock


def request(**overrides: Any) -> LLMRequest:
    base: dict[str, Any] = {
        "system": SYSTEM,
        "contents": (UserMessage("When is my next payment?"),),
        "tools": (GET_MY_ORDERS_DECLARATION,),
        "tool_mode": "auto",
        "response_schema": FinalAnswer,
    }
    base.update(overrides)
    return LLMRequest(**base)


def tool_call(name: str, args: Any, call_id: str = "call_1") -> dict[str, Any]:
    arguments = args if isinstance(args, str) else json.dumps(args)
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def completion(
    tool_calls: list[dict[str, Any]] | None = None,
    *,
    content: str | None = None,
    finish: str = "tool_calls",
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
    }


def ok(body: dict[str, Any] | None = None) -> httpx.Response:
    return httpx.Response(200, json=body or completion([tool_call(SUBMIT_ANSWER, FINAL)]))


def error(
    code: int,
    message: str = "",
    *,
    error_type: str = "invalid_request_error",
    error_code: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    err: dict[str, Any] = {"message": message, "type": error_type}
    if error_code is not None:
        err["code"] = error_code
    return httpx.Response(code, json={"error": err}, headers=headers)


def without_estimate(attempt: dict[str, Any]) -> dict[str, Any]:
    """A trace attempt minus ``est_tokens``, after checking it is a positive count."""
    out = dict(attempt)
    est = out.pop("est_tokens")
    assert isinstance(est, int) and est > 0
    return out


TPM_MESSAGE = (
    "Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01abcXYZ` "
    "service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 7000, Requested 2000."
)
# The request alone exceeds the per-minute limit: no wait can make it fit.
TPM_413_MESSAGE = (
    "Request too large for model `openai/gpt-oss-120b` in organization `org_01abcXYZ` "
    "service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 8350, "
    "please reduce your message size and try again."
)
# The request fits the limit; the model's rolling window is what is full.
TPM_413_SATURATED_MESSAGE = (
    "Request too large for model `openai/gpt-oss-120b` in organization `org_01abcXYZ` "
    "service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 6500, "
    "please reduce your message size and try again."
)
# No provider values: the client estimate decides.
TPM_413_NO_VALUES_MESSAGE = (
    "Request too large for model `openai/gpt-oss-120b` on tokens per minute (TPM), "
    "please reduce your message size and try again."
)
TPD_MESSAGE = (
    "Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01abcXYZ` "
    "service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 199000."
)


# --- request shape ----------------------------------------------------------------------------


def test_auto_mode_request_shape() -> None:
    client, server, _, _ = make_client([ok()])
    client.generate(request())
    (req,) = server.requests
    assert req.method == "POST"
    assert str(req.url) == GROQ_BASE_URL + CHAT_COMPLETIONS_PATH
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = server.bodies[0]
    assert body["model"] == PRIMARY
    assert [t["function"]["name"] for t in body["tools"]] == ["get_my_orders", SUBMIT_ANSWER]
    assert all(t["type"] == "function" for t in body["tools"])
    assert body["tools"][0]["function"]["parameters"] == GET_MY_ORDERS_DECLARATION["parameters"]
    assert body["tools"][1]["function"]["parameters"] == FinalAnswer.model_json_schema()
    assert body["tool_choice"] == "required"
    assert body["parallel_tool_calls"] is False
    assert body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] == 1024
    assert "response_format" not in body
    assert body["messages"][0] == {"role": "system", "content": SYSTEM}
    assert body["messages"][1] == {"role": "user", "content": "When is my next payment?"}


def test_none_mode_forces_submit_answer_only() -> None:
    client, server, _, _ = make_client([ok()])
    client.generate(request(tool_mode="none"))
    body = server.bodies[0]
    assert [t["function"]["name"] for t in body["tools"]] == [SUBMIT_ANSWER]
    assert body["tool_choice"] == {"type": "function", "function": {"name": SUBMIT_ANSWER}}
    assert body["parallel_tool_calls"] is False


def test_auto_mode_without_order_tool_still_requires_submit_answer() -> None:
    client, server, _, _ = make_client([ok()])
    client.generate(request(tools=()))  # fraud mode withholds get_my_orders
    body = server.bodies[0]
    assert [t["function"]["name"] for t in body["tools"]] == [SUBMIT_ANSWER]
    assert body["tool_choice"] == "required"


def test_request_overrides_reasoning_effort_and_max_tokens() -> None:
    client, server, _, _ = make_client([ok()], reasoning_effort="high")
    client.generate(request(max_output_tokens=700))
    body = server.bodies[0]
    assert (body["reasoning_effort"], body["max_completion_tokens"]) == ("high", 700)


def test_no_schema_request_sends_plain_tools() -> None:
    client, server, _, _ = make_client([ok(completion(content="hi", finish="stop"))])
    resp = client.generate(request(response_schema=None))
    body = server.bodies[0]
    assert [t["function"]["name"] for t in body["tools"]] == ["get_my_orders"]
    assert body["tool_choice"] == "auto"
    assert resp.text == "hi" and resp.malformed


# --- response normalization -------------------------------------------------------------------


def test_submit_answer_becomes_final_json() -> None:
    client, _, _, _ = make_client([ok()])
    resp = client.generate(request())
    assert resp.final_json == FINAL
    assert resp.function_calls == ()
    assert not resp.malformed
    assert resp.model_id == PRIMARY
    assert resp.finish_reason == "tool_calls"
    assert resp.raw_model_turn["role"] == "assistant"


def test_get_my_orders_becomes_function_call() -> None:
    body = completion([tool_call("get_my_orders", {"order_id": "ord_1"}, "call_abc")])
    client, _, _, _ = make_client([ok(body)])
    resp = client.generate(request())
    assert [(c.name, c.args, c.call_id) for c in resp.function_calls] == [
        ("get_my_orders", {"order_id": "ord_1"}, "call_abc")
    ]
    assert resp.final_json is None
    assert resp.raw_model_turn == body["choices"][0]["message"]


def test_empty_arguments_mean_no_filters() -> None:
    client, _, _, _ = make_client([ok(completion([tool_call("get_my_orders", "")]))])
    resp = client.generate(request())
    assert resp.function_calls[0].args == {}


@pytest.mark.parametrize(
    "arguments",
    ['{"answer": "x"', "[1, 2]", '"text"', "not json"],
    ids=["truncated", "array", "string", "garbage"],
)
@pytest.mark.parametrize("name", [SUBMIT_ANSWER, "get_my_orders"])
def test_unparseable_or_non_object_args_are_malformed(name: str, arguments: str) -> None:
    body = completion([tool_call(name, arguments)])
    client, _, _, _ = make_client([ok(body)])
    resp = client.generate(request())
    assert resp.malformed
    assert resp.function_calls == () and resp.final_json is None
    assert resp.raw_model_turn == body["choices"][0]["message"]  # replayable for the repair


def test_text_only_reply_is_malformed() -> None:
    client, _, _, _ = make_client([ok(completion(content=json.dumps(FINAL), finish="stop"))])
    resp = client.generate(request())
    assert resp.malformed and resp.text == json.dumps(FINAL)


def test_no_choices_is_malformed() -> None:
    client, _, _, _ = make_client([httpx.Response(200, json={"choices": []})])
    assert client.generate(request()).malformed


def test_unknown_tool_is_passed_to_the_agent_not_executed_here() -> None:
    client, _, _, _ = make_client([ok(completion([tool_call("delete_orders", {})]))])
    resp = client.generate(request())
    assert [c.name for c in resp.function_calls] == ["delete_orders"]
    assert resp.final_json is None


def test_premature_submit_answer_next_to_a_lookup_goes_to_the_agent() -> None:
    calls = [tool_call("get_my_orders", {}, "c1"), tool_call(SUBMIT_ANSWER, FINAL, "c2")]
    client, _, _, _ = make_client([ok(completion(calls))])
    resp = client.generate(request())
    assert [c.name for c in resp.function_calls] == ["get_my_orders", SUBMIT_ANSWER]
    assert resp.final_json is None


# The shape Groq returns when gpt-oss writes the answer as text instead of calling a tool.
TOOL_USE_FAILED_GENERATION = (
    '{\n  "answer": "…",\n  "cited_policies": [],\n  "escalation_reason": "none",\n'
    '  "policy_applied": false\n}'
)


FAILED_GENERATION_MESSAGES = {
    "tool_use_failed": "Tool choice is required, but model did not call a tool",
    "output_parse_failed": (
        "Parsing failed. The model generated output that could not be parsed. "
        "Please adjust your prompt. See 'failed_generation' for more details."
    ),
}
FAILED_GENERATION_CODES = pytest.mark.parametrize("code", sorted(FAILED_GENERATION_MESSAGES))


def tool_use_failed(
    generation: Any = None, *, include: bool = True, code: str = "tool_use_failed"
) -> httpx.Response:
    err: dict[str, Any] = {
        "message": FAILED_GENERATION_MESSAGES[code],
        "type": "invalid_request_error",
        "code": code,
    }
    if include:
        err["failed_generation"] = generation
    return httpx.Response(400, json={"error": err})


@FAILED_GENERATION_CODES
@pytest.mark.parametrize("tool_mode", ["auto", "none"])
def test_tool_use_failed_answer_is_recovered_as_final_json(tool_mode: str, code: str) -> None:
    client, server, _, _ = make_client([tool_use_failed(TOOL_USE_FAILED_GENERATION, code=code)])
    resp = client.generate(request(tool_mode=tool_mode))
    assert resp.final_json == {
        "answer": "…",
        "cited_policies": [],
        "escalation_reason": "none",
        "policy_applied": False,
    }
    assert not resp.malformed and resp.function_calls == ()
    assert resp.raw_model_turn is None
    assert resp.finish_reason == code
    assert len(server.requests) == 1
    assert [without_estimate(a.to_dict()) for a in resp.attempts] == [
        {
            "model": PRIMARY,
            "reason": "primary",
            "status": "ok",
            "error_class": None,
            "latency_ms": 0,
            "paced_ms": 0,
            "recovered": code,
        }
    ]


@pytest.mark.parametrize(
    "generation",
    [
        '{\n  "answer": "cut off',  # partial JSON
        "not json at all",
        '["a", "list"]',
        json.dumps({**FINAL, "policy_applied": "yes"}),  # fails the schema
        json.dumps({"answer": "Synthetic reply."}),  # missing fields
        json.dumps({**FINAL, "extra": 1}),
        json.dumps({"name": "get_my_orders", "arguments": {}}),  # a lookup-like call
        json.dumps({"name": SUBMIT_ANSWER, "arguments": FINAL}),
        "",
        17,
        {"answer": "an object, not a string"},
    ],
)
@FAILED_GENERATION_CODES
def test_tool_use_failed_without_a_valid_answer_is_malformed(generation: Any, code: str) -> None:
    client, server, _, _ = make_client([tool_use_failed(generation, code=code)])
    resp = client.generate(request())
    assert resp.malformed and resp.raw_model_turn is None
    assert len(server.requests) == 1  # one attempt: no same-model retry, no fallback
    assert [without_estimate(a.to_dict()) for a in resp.attempts] == [
        {
            "model": PRIMARY,
            "reason": "primary",
            "status": "ok",
            "error_class": None,
            "latency_ms": 0,
            "paced_ms": 0,
        }
    ]


@FAILED_GENERATION_CODES
@pytest.mark.parametrize(
    "make_response",
    [
        lambda code: tool_use_failed(include=False, code=code),
        lambda code: tool_use_failed(None, code=code),
        lambda code: error(400, "Failed to call a function.", error_code=code),
    ],
)
def test_tool_use_failed_without_failed_generation_is_malformed(
    make_response: Callable[[str], httpx.Response], code: str
) -> None:
    client, server, _, _ = make_client([make_response(code)])
    resp = client.generate(request())
    assert resp.malformed and resp.raw_model_turn is None
    assert len(server.requests) == 1
    assert [(a.status, a.recovered) for a in resp.attempts] == [("ok", None)]


@FAILED_GENERATION_CODES
def test_tool_use_failed_is_not_recovered_without_an_answer_schema(code: str) -> None:
    client, _, _, _ = make_client([tool_use_failed(TOOL_USE_FAILED_GENERATION, code=code)])
    resp = client.generate(request(response_schema=None))
    assert resp.malformed


@pytest.mark.parametrize(
    "response",
    [
        error(400, "Some other invalid request."),
        error(400, "Some other invalid request.", error_code="invalid_value"),
        httpx.Response(400, json={"error": "tool_use_failed"}),  # no error object
        httpx.Response(400, text="tool_use_failed"),  # not JSON
        error(422, "Unprocessable.", error_code="tool_use_failed"),  # not a 400
        error(422, "Unprocessable.", error_code="output_parse_failed"),  # not a 400
        error(400, "Parsing failed.", error_code="json_validate_failed"),  # another code
    ],
)
def test_other_4xx_stay_bad_request(response: httpx.Response) -> None:
    client, server, _, _ = make_client([response])
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "bad_request"
    assert len(server.requests) == 1


def test_content_filter_is_blocked_safety() -> None:
    body = completion(content="", finish="content_filter")
    client, _, _, _ = make_client([ok(body)])
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "blocked_safety"


def test_usage_mapping_is_none_safe() -> None:
    assert to_usage(None).to_dict() == {"input": 0, "output": 0, "cached": 0, "thoughts": 0}
    assert to_usage(
        {
            "prompt_tokens": 3300,
            "completion_tokens": 250,
            "prompt_tokens_details": {"cached_tokens": 2048},
            "completion_tokens_details": {"reasoning_tokens": 120},
        }
    ).to_dict() == {"input": 3300, "output": 250, "cached": 2048, "thoughts": 120}
    assert to_usage(
        {
            "prompt_tokens": 10,
            "completion_tokens": None,
            "prompt_tokens_details": None,
            "completion_tokens_details": {"reasoning_tokens": None},
        }
    ).to_dict() == {"input": 10, "output": 0, "cached": 0, "thoughts": 0}


def test_usage_reaches_the_response() -> None:
    usage = {
        "prompt_tokens": 900,
        "completion_tokens": 80,
        "prompt_tokens_details": {"cached_tokens": 512},
        "completion_tokens_details": {"reasoning_tokens": 30},
    }
    client, _, _, _ = make_client([ok(completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage))])
    resp = client.generate(request())
    assert resp.usage.to_dict() == {"input": 900, "output": 80, "cached": 512, "thoughts": 30}


# --- history mapping --------------------------------------------------------------------------


def test_history_replays_the_assistant_turn_unchanged_and_pairs_tool_results() -> None:
    lookup = completion([tool_call("get_my_orders", {"merchant": "Demo"}, "call_9")])
    client, server, _, _ = make_client([ok(lookup), ok()])
    first = client.generate(request())
    history = (
        UserMessage("When is my next payment?"),
        ModelTurn(first.raw_model_turn),
        ToolResult("get_my_orders", {"status": "ok", "orders": []}, "call_9"),
    )
    second = client.generate(request(contents=history, tool_mode="none"))
    assert second.final_json == FINAL
    messages = server.bodies[1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool"]
    assert messages[2] == lookup["choices"][0]["message"]
    assert messages[3] == {
        "role": "tool",
        "tool_call_id": "call_9",
        "content": json.dumps({"status": "ok", "orders": []}),
    }


def test_replayed_submit_answer_is_acknowledged_before_the_repair_note() -> None:
    turn = completion([tool_call(SUBMIT_ANSWER, FINAL, "call_s")])["choices"][0]["message"]
    messages = to_messages(SYSTEM, (UserMessage("q"), ModelTurn(turn), UserMessage("repair")))
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "tool", "user"]
    assert messages[3] == {
        "role": "tool",
        "tool_call_id": "call_s",
        "content": json.dumps({"status": "received"}),
    }


def test_replayed_malformed_call_gets_a_data_free_reply() -> None:
    turn = completion([tool_call("get_my_orders", "{bad", "call_m")])["choices"][0]["message"]
    messages = to_messages(SYSTEM, (UserMessage("q"), ModelTurn(turn)))
    assert messages[-1] == {
        "role": "tool",
        "tool_call_id": "call_m",
        "content": json.dumps({"status": "not_executed"}),
    }


def test_rejected_calls_from_the_agent_keep_calls_and_replies_paired() -> None:
    calls = [tool_call("get_my_orders", {}, "c1"), tool_call("get_my_orders", {}, "c2")]
    turn = completion(calls)["choices"][0]["message"]
    history = (
        UserMessage("q"),
        ModelTurn(turn),
        ToolResult("get_my_orders", {"status": "ok"}, "c1"),
        ToolResult("get_my_orders", {"status": "rejected"}, "c2"),
    )
    messages = to_messages(SYSTEM, history)
    assert [(m["role"], m.get("tool_call_id")) for m in messages[2:]] == [
        ("assistant", None),
        ("tool", "c1"),
        ("tool", "c2"),
    ]


def test_tool_result_without_call_id_matches_by_name() -> None:
    turn = completion([tool_call("get_my_orders", {}, "c7")])["choices"][0]["message"]
    history = (UserMessage("q"), ModelTurn(turn), ToolResult("get_my_orders", {"status": "ok"}))
    assert to_messages(SYSTEM, history)[-1]["tool_call_id"] == "c7"


def test_foreign_model_turn_is_rejected() -> None:
    with pytest.raises(TypeError):
        to_messages(SYSTEM, (ModelTurn({"role": "model", "parts": []}),))


# --- error classification and the §7 table ----------------------------------------------------

ERROR_TABLE = [
    (error(401, "Invalid API Key", error_type="invalid_request_error"), "auth_billing"),
    (error(403, "Forbidden", error_type="permissions_error"), "auth_billing"),
    (error(404, "The model does not exist", error_code="model_not_found"), "model_not_found"),
    (error(408, "Request timeout"), "timeout"),
    (error(413, "Request Entity Too Large"), "bad_request"),
    (error(400, "messages[0].name is not supported"), "bad_request"),
    (error(422, "Unprocessable"), "bad_request"),
    (error(429, TPM_MESSAGE, headers={"retry-after": "2"}), "rate_limit_minute"),
    (error(429, TPD_MESSAGE), "quota_daily"),
    (
        error(429, "Rate limit reached", headers={"x-ratelimit-remaining-requests": "0"}),
        "quota_daily",
    ),
    (error(429, "Rate limit reached on requests per day (RPD)"), "quota_daily"),
    (error(498, "Flex tier capacity exceeded"), "overloaded"),
    (error(503, "Service Unavailable"), "overloaded"),
    (error(500, "Internal Server Error"), "server_5xx"),
    (error(502, "Bad Gateway"), "server_5xx"),
    (httpx.ReadTimeout("timed out"), "timeout"),
    (httpx.ConnectError("connection refused"), "server_5xx"),
    (httpx.Response(200, content=b"<html>oops</html>"), "server_5xx"),
]


@pytest.mark.parametrize(("outcome", "kind"), ERROR_TABLE, ids=[f"{k}" for _, k in ERROR_TABLE])
def test_error_mapping(outcome: Outcome, kind: str) -> None:
    client, _, _, _ = make_client([outcome, outcome, outcome], fallback_model=None, max_attempts=1)
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == kind
    if kind == "auth_billing":
        assert isinstance(info.value, AuthBillingError)


def test_quota_daily_fails_over_and_disables_the_model_for_the_batch() -> None:
    client, server, _, _ = make_client([error(429, TPD_MESSAGE), ok(), ok()])
    resp = client.generate(request())
    assert server.models_called == [PRIMARY, FALLBACK]
    assert resp.fallback_used
    assert [(a.model, a.status, a.error_class) for a in resp.attempts] == [
        (PRIMARY, "fallback", "quota_daily"),
        (FALLBACK, "ok", None),
    ]
    client.generate(request())
    assert server.models_called[-1] == FALLBACK  # primary stays disabled


def test_rate_limit_minute_fails_over_to_the_fallback_first() -> None:
    client, server, sleeps, _ = make_client(
        [error(429, TPM_MESSAGE, headers={"retry-after": "3"}), ok()]
    )
    resp = client.generate(request())
    assert server.models_called == [PRIMARY, FALLBACK]  # separate bucket: no wait needed
    assert [(a.model, a.status, a.error_class) for a in resp.attempts] == [
        (PRIMARY, "fallback", "rate_limit_minute"),
        (FALLBACK, "ok", None),
    ]
    assert sleeps == []


def test_rate_limit_minute_retry_waits_for_retry_after() -> None:
    client, server, sleeps, clock = make_client(
        [error(429, TPM_MESSAGE, headers={"retry-after": "3"}), ok()],
        fallback_model=None,
    )
    resp = client.generate(request(deadline=clock.t + 30))
    assert server.models_called == [PRIMARY, PRIMARY]
    assert [(a.status, a.error_class) for a in resp.attempts] == [
        ("retry", "rate_limit_minute"),
        ("ok", None),
    ]
    # Not re-sent before retry-after has elapsed (runner backoff + pacing wait for the rest).
    assert server.sent_at[1] - server.sent_at[0] == pytest.approx(3.0)
    assert resp.attempts[1].paced_ms is not None and resp.attempts[1].paced_ms > 0
    assert sum(sleeps) == pytest.approx(3.0)


def test_retry_after_is_remembered_for_the_next_call_on_that_model() -> None:
    client, server, sleeps, clock = make_client(
        [error(429, TPM_MESSAGE, headers={"retry-after": "5"}), ok(), ok()]
    )
    client.generate(request(deadline=clock.t + 30))
    resp = client.generate(request(deadline=clock.t + 30))
    assert server.models_called == [PRIMARY, FALLBACK, PRIMARY]
    assert resp.attempts[0].paced_ms == 5000
    assert sleeps == [pytest.approx(5.0)]


def test_retry_after_beyond_the_deadline_is_not_waited_for() -> None:
    client, server, sleeps, clock = make_client(
        [error(429, TPM_MESSAGE, headers={"retry-after": "50"})],
        fallback_model=None,
        max_attempts=2,
    )
    with pytest.raises(ProviderError) as info:
        client.generate(request(deadline=clock.t + 20))
    assert info.value.kind == "rate_limit_minute"
    assert len(server.requests) == 1  # the retry was refused client-side, never sent
    assert sum(sleeps) < 20


def test_overloaded_primary_fails_over_to_fallback() -> None:
    client, server, _, _ = make_client([error(503, "over capacity"), ok()])
    resp = client.generate(request())
    assert resp.final_json == FINAL
    assert server.models_called == [PRIMARY, FALLBACK]
    assert resp.model_id == FALLBACK and resp.fallback_used
    assert [(a.model, a.reason, a.status, a.error_class) for a in resp.attempts] == [
        (PRIMARY, "primary", "fallback", "overloaded"),
        (FALLBACK, "failover", "ok", None),
    ]


def test_fallback_changes_only_the_model() -> None:
    client, server, _, _ = make_client([error(500, "oops"), ok()])
    client.generate(request())
    first, second = server.bodies
    assert (first.pop("model"), second.pop("model")) == (PRIMARY, FALLBACK)
    assert first == second
    assert (
        server.requests[0].headers["authorization"] == server.requests[1].headers["authorization"]
    )


def test_auth_failure_latches_the_breaker() -> None:
    client, server, _, _ = make_client([error(401, "Invalid API Key")])
    with pytest.raises(AuthBillingError):
        client.generate(request())
    with pytest.raises(AuthBillingError):
        client.generate(request())
    assert len(server.requests) == 1


def test_413_is_logged_clearly(caplog: pytest.LogCaptureFixture) -> None:
    client, _, _, _ = make_client([error(413, "Request Entity Too Large")], fallback_model=None)
    with (
        caplog.at_level(logging.WARNING, logger="support_agent.llm.groq"),
        pytest.raises(ProviderError) as info,
    ):
        client.generate(request())
    assert info.value.kind == "bad_request"
    assert "too large" in info.value.message
    assert any("HTTP 413" in r.getMessage() for r in caplog.records)
    assert all(KEY not in r.getMessage() for r in caplog.records)


def tpm_413(
    message: str = TPM_413_SATURATED_MESSAGE, headers: dict[str, str] | None = None
) -> httpx.Response:
    return error(
        413,
        message,
        error_type="tokens",
        error_code="rate_limit_exceeded",
        headers=headers,
    )


def test_413_tpm_with_a_request_within_the_budget_is_a_minute_rate_limit() -> None:
    client, server, sleeps, clock = make_client([tpm_413(), ok(), ok()], tpm_budget=8000)
    resp = client.generate(request(deadline=clock.t + 30))
    assert server.models_called == [PRIMARY, FALLBACK]  # separate bucket: fallback-eligible
    assert [(a.model, a.status, a.error_class) for a in resp.attempts] == [
        (PRIMARY, "fallback", "rate_limit_minute"),
        (FALLBACK, "ok", None),
    ]
    assert sleeps == []
    # No retry-after: the primary stays blocked until its rolling minute frees, so the next
    # call within the case deadline goes to the fallback without being sent to the primary.
    nxt = client.generate(request(deadline=clock.t + 30))
    assert server.models_called == [PRIMARY, FALLBACK, FALLBACK]
    assert [(a.model, a.status, a.error_class) for a in nxt.attempts] == [
        (PRIMARY, "fallback", "rate_limit_minute"),
        (FALLBACK, "ok", None),
    ]
    assert "beyond the case deadline" in (nxt.attempts[0].detail or "")


def test_413_tpm_honours_retry_after_before_the_next_primary_call() -> None:
    client, server, sleeps, clock = make_client(
        [tpm_413(headers={"retry-after": "4"}), ok(), ok()], tpm_budget=8000
    )
    client.generate(request(deadline=clock.t + 30))
    resp = client.generate(request(deadline=clock.t + 30))
    assert server.models_called == [PRIMARY, FALLBACK, PRIMARY]
    assert resp.attempts[0].paced_ms == 4000
    assert sleeps == [pytest.approx(4.0)]


def test_413_tpm_without_fallback_retries_after_the_window_frees() -> None:
    client, server, _, clock = make_client([tpm_413(), ok()], tpm_budget=8000, fallback_model=None)
    resp = client.generate(request(deadline=clock.t + 120))
    assert server.models_called == [PRIMARY, PRIMARY]
    assert [(a.status, a.error_class) for a in resp.attempts] == [
        ("retry", "rate_limit_minute"),
        ("ok", None),
    ]
    assert server.sent_at[1] - server.sent_at[0] == pytest.approx(60.0)


@pytest.mark.parametrize("budget", [500, 0], ids=["over_budget", "pacing_disabled"])
def test_413_tpm_with_a_request_over_the_budget_stays_bad_request(
    budget: int, caplog: pytest.LogCaptureFixture
) -> None:
    client, server, _, clock = make_client(
        [tpm_413(TPM_413_NO_VALUES_MESSAGE), ok()], tpm_budget=budget
    )
    with (
        caplog.at_level(logging.WARNING, logger="support_agent.llm.groq"),
        pytest.raises(ProviderError) as info,
    ):
        client.generate(request(deadline=clock.t + 30))
    assert info.value.kind == "bad_request"
    assert len(server.requests) == 1  # no fallback, no retry: it must not loop
    (attempt,) = info.value.attempts
    assert (attempt.status, attempt.error_class) == ("failed", "bad_request")
    assert attempt.est_tokens is not None and attempt.est_tokens > max(budget, 1024)
    assert f"~{attempt.est_tokens} estimated tokens" in info.value.message
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert f"~{attempt.est_tokens} estimated tokens" in logged
    assert f"GROQ_TPM_BUDGET={budget}" in logged and "bad_request" in logged


def test_413_without_provider_values_falls_back_to_the_estimate() -> None:
    no_values = tpm_413(TPM_413_NO_VALUES_MESSAGE)
    assert classify_response(no_values, tpm_budget=8000).kind == "bad_request"
    assert classify_response(no_values, est_tokens=2000, tpm_budget=8000).kind == (
        "rate_limit_minute"
    )
    assert classify_response(no_values, est_tokens=9000, tpm_budget=8000).kind == "bad_request"
    too_large = error(413, "Request Entity Too Large")
    assert classify_response(too_large, est_tokens=2000, tpm_budget=8000).kind == "bad_request"


def test_413_requested_over_the_provider_limit_is_bad_request_whatever_the_estimate() -> None:
    # R-02 #2: the provider says the request alone is larger than the limit.
    err = classify_response(tpm_413(TPM_413_MESSAGE), est_tokens=2000, tpm_budget=8000)
    assert err.kind == "bad_request"
    assert "Limit 8000, Requested 8350" in err.message
    for est, budget in [(None, 8000), (2000, 0), (100, 100000)]:
        assert classify_response(
            tpm_413(TPM_413_MESSAGE), est_tokens=est, tpm_budget=budget
        ).kind == ("bad_request")


def test_413_requested_within_the_provider_limit_is_a_minute_rate_limit_whatever_the_estimate() -> (
    None
):
    for est, budget in [(None, 8000), (9000, 8000), (2000, 0)]:
        err = classify_response(tpm_413(), est_tokens=est, tpm_budget=budget)
        assert err.kind == "rate_limit_minute"
        assert "Limit 8000, Requested 6500" in err.message
    at_limit = TPM_413_SATURATED_MESSAGE.replace("Requested 6500", "Requested 8000")
    assert classify_response(tpm_413(at_limit), est_tokens=9000, tpm_budget=8000).kind == (
        "rate_limit_minute"
    )
    # Values without a per-minute-limit message are not treated as a full window.
    body_limit = error(413, "Payload too large: Limit 8000, Requested 6500")
    assert classify_response(body_limit, est_tokens=2000, tpm_budget=8000).kind == "bad_request"


def test_413_requested_over_the_provider_limit_is_never_retried_or_failed_over(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, server, sleeps, clock = make_client(
        [tpm_413(TPM_413_MESSAGE), ok(), ok()], tpm_budget=8000
    )
    req = request(deadline=clock.t + 180)
    assert (
        client.pacer.estimate(_request_chars(to_messages(req.system, req.contents), req), 1024)
        < 8000
    )
    with (
        caplog.at_level(logging.WARNING, logger="support_agent.llm.groq"),
        pytest.raises(ProviderError) as info,
    ):
        client.generate(req)
    assert info.value.kind == "bad_request"
    assert len(server.requests) == 1  # no retry, no fallback, no pacing block
    assert sleeps == []
    (attempt,) = info.value.attempts
    assert (attempt.model, attempt.status, attempt.error_class) == (
        PRIMARY,
        "failed",
        "bad_request",
    )
    assert client.pacer.window_free_in(PRIMARY) == 60.0  # released; nothing blocks the model
    assert client.generate(request(deadline=clock.t + 180)).model_id == PRIMARY
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "Limit 8000, Requested 8350" in logged and "bad_request" in logged


def test_failed_attempts_carry_a_scrubbed_provider_detail() -> None:
    leak = f"{TPM_413_MESSAGE} key={KEY} auth=Bearer sk-other-token-42 " + "x" * 400
    client, _, _, clock = make_client([error(500, leak, error_code="internal_error"), ok()])
    resp = client.generate(request(deadline=clock.t + 30))
    failed, succeeded = resp.attempts
    assert failed.status == "fallback"
    detail = failed.detail
    assert detail is not None
    assert detail.startswith("HTTP 500 internal_error: Request too large for model")
    for secret in (KEY, "sk-other-token-42", "org_01abcXYZ"):
        assert secret not in detail
    assert "org_[REDACTED]" in detail
    assert len(detail.split(": ", 1)[1]) <= 200
    assert succeeded.detail is None
    assert "detail" not in succeeded.to_dict()
    assert failed.to_dict()["detail"] == detail


def test_detail_falls_back_to_the_error_type_and_covers_retries_and_terminal_failures() -> None:
    client, _, _, clock = make_client(
        [error(502, "Bad Gateway", error_type="server_error")] * 2, fallback_model=None
    )
    with pytest.raises(ProviderError) as info:
        client.generate(request(deadline=clock.t + 30))
    assert [(a.status, a.detail) for a in info.value.attempts] == [
        ("retry", "HTTP 502 server_error: Bad Gateway"),
        ("failed", "HTTP 502 server_error: Bad Gateway"),
    ]


def test_transport_failures_carry_the_client_side_reason() -> None:
    client, _, _, _ = make_client([httpx.ReadTimeout("timed out"), ok()])
    resp = client.generate(request())
    assert resp.attempts[0].detail == "client timeout (ReadTimeout)"
    assert resp.attempts[1].detail is None


def test_est_tokens_is_the_pacing_estimate_of_every_attempt() -> None:
    client, _, _, _ = make_client([error(503, "over capacity"), ok()])
    req = request()
    expected = client.pacer.estimate(
        _request_chars(to_messages(req.system, req.contents), req), 1024
    )
    resp = client.generate(req)
    assert [a.est_tokens for a in resp.attempts] == [expected, expected]
    assert all(a.to_dict()["est_tokens"] == expected for a in resp.attempts)


def test_error_messages_hide_the_key_and_organisation_id() -> None:
    leaky = error(429, f"{TPM_MESSAGE} key={KEY}", headers={"retry-after": "1"})
    client, _, _, _ = make_client([leaky], fallback_model=None, max_attempts=1)
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert KEY not in str(info.value)
    assert "org_01abcXYZ" not in str(info.value)
    assert "org_[REDACTED]" in str(info.value)


def test_timeout_is_capped_by_the_case_deadline() -> None:
    seen: list[Any] = []

    def capture(req: httpx.Request) -> httpx.Response:
        seen.append(req.extensions["timeout"])
        return ok()

    client, _, _, clock = make_client([capture], timeout_s=10.0)
    client.generate(request(deadline=clock.t + 4))
    assert seen[0]["read"] == pytest.approx(4.0)


def test_groq_client_does_not_apply_the_gemini_minimum_timeout() -> None:
    client, _, _, _ = make_client([], timeout_s=3.0)
    assert client.runner.timeout_s == 3.0
    assert client.runner.min_attempt_s < 1.0


# --- pacing -----------------------------------------------------------------------------------


def usage(prompt: int, completion_tokens: int, cached: int = 0) -> dict[str, Any]:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion_tokens,
        "prompt_tokens_details": {"cached_tokens": cached},
    }


def test_pacing_waits_when_the_minute_budget_is_used() -> None:
    body = completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage(4000, 500))
    client, server, sleeps, clock = make_client([ok(body), ok(body)], tpm_budget=6000)
    first = client.generate(request(deadline=clock.t + 120))
    assert first.attempts[0].paced_ms == 0
    assert client.pacer.used(PRIMARY) == 4500  # the estimate was replaced by reported usage
    second = client.generate(request(deadline=clock.t + 120))
    assert sleeps == [pytest.approx(60.0)]
    assert second.attempts[0].paced_ms == 60000
    assert second.attempts[0].to_dict()["paced_ms"] == 60000
    assert server.sent_at[1] - server.sent_at[0] == pytest.approx(60.0)
    assert second.model_id == PRIMARY


def test_cached_input_does_not_count_toward_the_budget() -> None:
    body = completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage(4000, 500, cached=3000))
    client, _, sleeps, clock = make_client([ok(body), ok(body)], tpm_budget=6000)
    client.generate(request(deadline=clock.t + 120))
    assert client.pacer.used(PRIMARY) == 1500
    client.generate(request(deadline=clock.t + 120))
    assert sleeps == []


def test_pacing_wait_beyond_the_deadline_goes_to_the_fallback_unsent() -> None:
    body = completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage(5000, 500))
    client, server, sleeps, clock = make_client([ok(body), ok(body)], tpm_budget=6000)
    client.generate(request(deadline=clock.t + 30))
    resp = client.generate(request(deadline=clock.t + 30))
    assert server.models_called == [PRIMARY, FALLBACK]  # separate per-model bucket
    assert sleeps == []
    assert [(a.model, a.status, a.error_class, a.paced_ms) for a in resp.attempts] == [
        (PRIMARY, "fallback", "rate_limit_minute", 0),
        (FALLBACK, "ok", None, 0),
    ]


def groq_default_deadline_s() -> float:
    return Settings.from_env({"LLM_PROVIDER": "groq", "GROQ_API_KEY": KEY}).case_deadline_s


def test_third_call_waits_and_is_sent_when_both_model_windows_are_full() -> None:
    # R-02 #1: two 5,500-token calls fill both 8,000-token model windows; the third call must
    # wait (within the default Groq case deadline) and be sent, never fail unsent.
    deadline_s = groq_default_deadline_s()
    body = completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage(5000, 500))
    client, server, sleeps, clock = make_client([ok(body)] * 3, tpm_budget=8000)

    assert client.generate(request(deadline=clock.t + deadline_s)).model_id == PRIMARY
    clock.t += 5
    # The reviewer's sequence: the primary's pacing wait does not fit what is left of that
    # case's deadline, so call 2 goes to the fallback unsent to the primary.
    assert client.generate(request(deadline=clock.t + 30)).model_id == FALLBACK
    assert sleeps == []
    clock.t += 5
    assert client.pacer.used(PRIMARY) == client.pacer.used(FALLBACK) == 5500

    third = client.generate(request(deadline=clock.t + deadline_s))
    assert server.models_called == [PRIMARY, FALLBACK, PRIMARY]
    assert [(a.model, a.status, a.error_class, a.paced_ms) for a in third.attempts] == [
        (PRIMARY, "ok", None, 50000),
    ]
    assert sleeps == [pytest.approx(50.0)]
    assert server.sent_at[-1] == pytest.approx(1060.0)  # as soon as the primary's minute frees


def test_a_paced_batch_at_the_default_groq_deadline_sends_every_call() -> None:
    # Sequential saturating calls (as in a 35-50-case run) wait for the window instead of
    # being consumed as unsent rate_limit_minute failures.
    deadline_s = groq_default_deadline_s()
    body = completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage(5000, 500))
    calls = 12
    client, server, sleeps, clock = make_client([ok(body)] * calls, tpm_budget=8000)
    for _ in range(calls):
        resp = client.generate(request(deadline=clock.t + deadline_s))
        assert [(a.status, a.error_class) for a in resp.attempts] == [("ok", None)]
        clock.t += 1
    assert len(server.requests) == calls  # every call sent exactly once
    assert all(wait <= 60.0 for wait in sleeps)


def test_min_call_interval_spaces_calls() -> None:
    client, server, sleeps, clock = make_client([ok(), ok()], min_call_interval_s=5.0)
    client.generate(request(deadline=clock.t + 60))
    clock.t += 2.0
    resp = client.generate(request(deadline=clock.t + 60))
    assert sleeps == [pytest.approx(3.0)]
    assert resp.attempts[0].paced_ms == 3000
    assert server.sent_at[1] - server.sent_at[0] == pytest.approx(5.0)


def test_pacing_disabled_never_waits() -> None:
    body = completion([tool_call(SUBMIT_ANSWER, FINAL)], usage=usage(7000, 900))
    client, _, sleeps, clock = make_client([ok(body)] * 3, tpm_budget=0, min_call_interval_s=0)
    for _ in range(3):
        client.generate(request(deadline=clock.t + 30))
    assert sleeps == []


def test_unprocessed_requests_release_their_estimate() -> None:
    client, _, _, _ = make_client([error(500, "oops"), ok()], tpm_budget=6000)
    client.generate(request())
    # The 500 on the primary was released; only the fallback's settled usage remains.
    assert client.pacer.used(PRIMARY) == 0
    assert client.pacer.used(FALLBACK) == 1100


def test_token_pacer_estimate_calibrates_from_reported_usage() -> None:
    clock = Clock()
    pacer = TokenPacer(tpm_budget=8000, min_interval_s=0, clock=clock, sleep=lambda s: None)
    assert pacer.estimate(4000, 1000) == 2000  # chars / 4 + max completion tokens
    _, ticket = pacer.acquire(PRIMARY, 2000, None)
    from support_agent.llm.base import Usage

    pacer.settle(ticket, Usage(input=2000, output=100), request_chars=4000)
    assert pacer.chars_per_token == 2.0
    assert pacer.estimate(4000, 1000) == 3000
    clock.t += 60
    assert pacer.used(PRIMARY) == 0  # the rolling window forgets entries after a minute


def test_request_larger_than_the_budget_waits_for_an_empty_window() -> None:
    clock = Clock()
    waits: list[float] = []

    def sleep(s: float) -> None:
        waits.append(s)
        clock.t += s

    pacer = TokenPacer(tpm_budget=1000, min_interval_s=0, clock=clock, sleep=sleep)
    pacer.acquire(PRIMARY, 500, None)
    clock.t += 10
    waited, _ = pacer.acquire(PRIMARY, 5000, None)
    assert waited == pytest.approx(50.0)


# --- key isolation, wiring --------------------------------------------------------------------


def test_client_uses_only_the_groq_key_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key-should-not-be-used")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-should-not-be-used")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key-should-not-be-used")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:9")
    s = Settings.from_env(
        {
            "LLM_PROVIDER": "groq",
            "GROQ_API_KEY": KEY,
            "GOOGLE_API_KEY": "google-key-should-not-be-used",
            "CASE_DEADLINE_S": "90",
        }
    )
    server = Server([ok()])
    client = GroqClient(s, transport=httpx.MockTransport(server.handler))
    client.generate(request())
    headers = server.requests[0].headers
    assert headers["authorization"] == f"Bearer {KEY}"
    assert "should-not-be-used" not in json.dumps(dict(headers))
    assert client._http.trust_env is False  # inherited proxy/netrc variables are ignored
    assert KEY not in repr(client)


def test_missing_key_is_a_config_error() -> None:
    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        GroqClient(settings(api_key=None), transport=httpx.MockTransport(Server([]).handler))


def test_factory_selects_the_groq_client() -> None:
    client = make_llm_client(settings())
    assert isinstance(client, GroqClient)
    client.close()


def test_agent_end_to_end_over_groq_with_trace_pacing() -> None:
    """The unchanged agent loop drives the Groq adapter: lookup, then a forced submit_answer."""
    resources = Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))
    statics = AgentStatics.build(resources)
    lookup = completion([tool_call("get_my_orders", {}, "call_1")])
    client, server, _, clock = make_client([ok(lookup), ok()], tpm_budget=8000)
    case = Case(id="g1", user_id="u002", question="When is my next payment?")
    result = answer_case(resources, client, case, statics=statics, clock=clock)
    assert result.answer == FINAL["answer"]
    assert result.route == "tool"
    assert result.trace.error_class is None
    first, second = server.bodies
    assert first["tool_choice"] == "required"
    assert second["tool_choice"] == {"type": "function", "function": {"name": SUBMIT_ANSWER}}
    assert [m["role"] for m in second["messages"]] == ["system", "user", "assistant", "tool"]
    tool_reply = json.loads(second["messages"][3]["content"])
    assert tool_reply["status"] == "ok"
    for call in result.trace.to_dict()["llm_calls"]:
        assert call["attempts"][0]["paced_ms"] == 0
        assert call["attempts"][0]["est_tokens"] > 0
        assert "detail" not in call["attempts"][0]


def test_agent_trace_records_a_post_tool_413_detail_and_estimate() -> None:
    resources = Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))
    statics = AgentStatics.build(resources)
    lookup = completion([tool_call("get_my_orders", {}, "call_1")])
    client, server, _, clock = make_client([ok(lookup), tpm_413(), ok()], tpm_budget=8000)
    case = Case(id="g1", user_id="u002", question="When is my next payment?")
    result = answer_case(resources, client, case, statics=statics, clock=clock)
    assert result.answer == FINAL["answer"]
    assert server.models_called == [PRIMARY, PRIMARY, FALLBACK]
    trace = result.trace.to_dict()
    post_tool = trace["llm_calls"][1]
    failed, succeeded = post_tool["attempts"]
    assert failed["error_class"] == "rate_limit_minute"
    assert failed["detail"].startswith("HTTP 413 rate_limit_exceeded: Request too large")
    assert failed["est_tokens"] == succeeded["est_tokens"] > 0
    assert "detail" not in succeeded
    assert KEY not in result.trace.to_json()


@FAILED_GENERATION_CODES
def test_agent_trace_records_a_recovered_tool_use_failed_answer(code: str) -> None:
    resources = Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))
    statics = AgentStatics.build(resources)
    lookup = completion([tool_call("get_my_orders", {}, "call_1")])
    client, _, _, clock = make_client([ok(lookup), tool_use_failed(json.dumps(FINAL), code=code)])
    case = Case(id="g1", user_id="u002", question="When is my next payment?")
    result = answer_case(resources, client, case, statics=statics, clock=clock)
    assert result.answer == FINAL["answer"]
    assert result.route == "tool"
    assert result.trace.error_class is None
    first, second = result.trace.to_dict()["llm_calls"]
    assert "recovered" not in first["attempts"][0]
    assert second["outcome"] == "final"
    assert second["attempts"][0]["recovered"] == code


def test_recovered_answer_still_goes_through_the_agent_validator() -> None:
    resources = Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))
    statics = AgentStatics.build(resources)
    empty = json.dumps({**FINAL, "answer": ""})  # schema-valid, but the validator rejects it
    client, server, _, clock = make_client([tool_use_failed(empty), ok()])
    case = Case(id="g1", user_id="u002", question="How does Pay in 4 work?")
    result = answer_case(resources, client, case, statics=statics, clock=clock)
    assert result.answer == FINAL["answer"]
    assert len(server.requests) == 2  # the repair call ran
    trace = result.trace.to_dict()
    assert trace["repair_attempted"] is True
    assert trace["validator"][0] == {
        "check": "schema",
        "verdict": "fail",
        "detail": "answer is empty",
        "stage": "initial",
    }
    calls = trace["llm_calls"]
    assert [c["purpose"] for c in calls] == ["initial", "repair"]
    assert calls[0]["attempts"][0]["recovered"] == "tool_use_failed"


def test_run_config_records_groq_settings(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = importlib.util.spec_from_file_location("run_cases_cli", PROJECT_ROOT / "run_cases.py")
    assert spec is not None and spec.loader is not None
    run_cases = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, run_cases)  # dataclasses resolve by module name
    spec.loader.exec_module(run_cases)

    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps({"id": "g1", "user_id": "u002", "question": "How does Pay in 4 work?"}) + "\n"
    )
    answers = tmp_path / "run" / "answers.jsonl"
    server = Server([ok()])
    client = GroqClient(settings(), transport=httpx.MockTransport(server.handler))
    env = {
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": KEY,
        "GROQ_TPM_BUDGET": "7000",
        "GROQ_MIN_CALL_INTERVAL_S": "1.5",
        "CASE_DEADLINE_S": "90",
    }
    code = run_cases.main([str(cases), str(answers)], environ=env, llm=client)
    assert code == 0
    config = json.loads(answers.with_suffix(".config.json").read_text())
    assert config["provider"] == "groq"
    assert (config["primary_model"], config["fallback_model"]) == (PRIMARY, FALLBACK)
    assert config["reasoning_effort"] == "low"
    assert config["pacing"] == {"tpm_budget": 7000, "min_call_interval_s": 1.5}
    assert config["credential_env_var"] == "GROQ_API_KEY"
    assert KEY not in answers.with_suffix(".config.json").read_text()
    assert KEY not in answers.with_suffix(".trace.jsonl").read_text()
