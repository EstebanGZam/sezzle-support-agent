"""Gemini adapter: §7 error table, retry/fallback, config and normalization (no network).

The SDK client is replaced by a stub whose ``generate_content`` returns canned
``GenerateContentResponse`` objects or raises stubbed ``google.genai.errors`` / ``httpx``
exceptions, so every row of the architecture §7 table runs through the real ``GeminiClient``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from google.genai import errors, types

from support_agent.config import GEMINI_MIN_TIMEOUT_S, Secret, Settings
from support_agent.llm import (
    AuthBillingError,
    FinalAnswer,
    LLMRequest,
    ModelTurn,
    ProviderError,
    ToolResult,
    UserMessage,
)
from support_agent.llm.base import (
    MAX_BACKOFF_S,
    PRIMARY_BREAKER_THRESHOLD,
    PRIMARY_COOLDOWN_CALLS,
)
from support_agent.llm.gemini import (
    GEMINI_BASE_URL,
    GeminiClient,
    classify_exception,
    to_contents,
    to_usage,
)
from support_agent.tools import GET_MY_ORDERS_DECLARATION

PRIMARY = "gemini-3.5-flash-lite"
FALLBACK = "gemini-3.1-flash-lite"
KEY = "test-key-0123456789"
FINAL = {
    "answer": "Synthetic reply.",
    "escalation_reason": "none",
    "policy_applied": False,
    "cited_policies": [],
}


# --- stubs ------------------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class StubModels:
    def __init__(self, outcomes: list[Any], clock: Clock | None = None) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []
        self.clock = clock

    def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.calls.append({"model": model, "contents": contents, "config": config})
        outcome = self.outcomes.pop(0)
        if callable(outcome) and not isinstance(outcome, BaseException):
            outcome = outcome(self.clock)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    @property
    def models_called(self) -> list[str]:
        return [c["model"] for c in self.calls]


class StubSDK:
    def __init__(self, outcomes: list[Any], clock: Clock | None = None) -> None:
        self.models = StubModels(outcomes, clock)


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "provider": "gemini",
        "primary_model": PRIMARY,
        "fallback_model": FALLBACK,
        "api_key": Secret(KEY),
        "max_attempts": 2,
        "timeout_s": 10.0,
    }
    base.update(overrides)
    return Settings(**base)


def make_client(outcomes: list[Any], **overrides: Any) -> tuple[GeminiClient, StubSDK, list]:
    clock = Clock()
    sdk = StubSDK(outcomes, clock)
    sleeps: list[float] = []
    client = GeminiClient(settings(**overrides), client=sdk, sleep=sleeps.append, clock=clock)
    return client, sdk, sleeps


def request(**overrides: Any) -> LLMRequest:
    base: dict[str, Any] = {
        "system": "You are a support assistant for a fictional demo store.",
        "contents": (UserMessage("When is my next payment?"),),
        "tools": (GET_MY_ORDERS_DECLARATION,),
        "tool_mode": "auto",
    }
    base.update(overrides)
    return LLMRequest(**base)


def ok_response(
    parts: list[types.Part] | None = None,
    *,
    finish: types.FinishReason = types.FinishReason.STOP,
    usage: types.GenerateContentResponseUsageMetadata | None = None,
) -> types.GenerateContentResponse:
    parts = parts if parts is not None else [types.Part(text=json.dumps(FINAL))]
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(content=types.Content(role="model", parts=parts), finish_reason=finish)
        ],
        usage_metadata=usage,
    )


def api_error(
    code: int, status: str, message: str = "", details: list | None = None
) -> errors.APIError:
    body = {"error": {"code": code, "status": status, "message": message, "details": details or []}}
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, body)


def quota_failure(quota_id: str, value: str = "15") -> list[dict]:
    return [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [
                {
                    "quotaMetric": "generativelanguage.googleapis.com/generate_content_requests",
                    "quotaId": quota_id,
                    "quotaValue": value,
                }
            ],
        },
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"},
    ]


QUOTA_MSG = "You exceeded your current quota, please check your plan and billing details."
RATE_MINUTE = api_error(
    429, "RESOURCE_EXHAUSTED", QUOTA_MSG, quota_failure("GenerateRequestsPerMinutePerProject")
)
QUOTA_DAY = api_error(
    429, "RESOURCE_EXHAUSTED", QUOTA_MSG, quota_failure("GenerateRequestsPerDayPerProjectPerModel")
)
SERVER_503 = api_error(
    503, "UNAVAILABLE", "This model is currently experiencing high demand. Try again later."
)
SERVER_504 = api_error(
    504, "DEADLINE_EXCEEDED", "Deadline expired before operation could complete."
)
SERVER_500 = api_error(500, "INTERNAL", "Internal error")
NOT_FOUND = api_error(404, "NOT_FOUND", "models/x is not found for API version v1beta")
BAD_REQUEST = api_error(400, "INVALID_ARGUMENT", "Invalid JSON payload received.")
BAD_KEY = api_error(
    400,
    "INVALID_ARGUMENT",
    "API key not valid. Please pass a valid API key.",
    [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}],
)
READ_TIMEOUT = httpx.ReadTimeout("timed out")


# --- §7 table: classification ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RATE_MINUTE, "rate_limit_minute"),
        (api_error(429, "RESOURCE_EXHAUSTED", "Resource has been exhausted"), "rate_limit_minute"),
        (api_error(429, "RESOURCE_EXHAUSTED", QUOTA_MSG), "rate_limit_minute"),
        (QUOTA_DAY, "quota_daily"),
        (api_error(429, "RESOURCE_EXHAUSTED", "Quota exceeded: requests per day"), "quota_daily"),
        (api_error(429, "RESOURCE_EXHAUSTED", "Daily limit reached"), "quota_daily"),
        (
            api_error(
                429,
                "RESOURCE_EXHAUSTED",
                QUOTA_MSG,
                quota_failure("GenerateRequestsPerMinute", "0"),
            ),
            "quota_daily",
        ),
        (SERVER_500, "server_5xx"),
        (api_error(502, "", "Bad gateway"), "server_5xx"),
        (SERVER_503, "overloaded"),
        (api_error(503, "", "Service unavailable"), "overloaded"),
        (SERVER_504, "overloaded"),
        (api_error(504, "", "Gateway timeout"), "overloaded"),
        (READ_TIMEOUT, "timeout"),
        (httpx.ConnectTimeout("connect timed out"), "timeout"),
        (TimeoutError("timed out"), "timeout"),
        (api_error(408, "", "Request timeout"), "timeout"),
        (httpx.ConnectError("connection refused"), "server_5xx"),
        (NOT_FOUND, "model_not_found"),
        (BAD_REQUEST, "bad_request"),
        (api_error(400, "INVALID_ARGUMENT", "response_schema: invalid enum"), "bad_request"),
        (api_error(413, "", "Payload too large"), "bad_request"),
        (BAD_KEY, "auth_billing"),
        (api_error(401, "UNAUTHENTICATED", "Request had invalid credentials"), "auth_billing"),
        (api_error(403, "PERMISSION_DENIED", "Permission denied"), "auth_billing"),
        (api_error(403, "PERMISSION_DENIED", "Billing account disabled"), "auth_billing"),
        (api_error(400, "FAILED_PRECONDITION", "User location is not supported"), "auth_billing"),
        (api_error(400, "INVALID_ARGUMENT", "API key expired. Please renew."), "auth_billing"),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_classify_exception(exc: BaseException, expected: str) -> None:
    err = classify_exception(exc, model=PRIMARY)
    assert err is not None
    assert err.kind == expected
    assert err.model == PRIMARY
    assert isinstance(err, AuthBillingError) == (expected == "auth_billing")


def test_unrelated_exceptions_are_not_classified() -> None:
    assert classify_exception(ValueError("bug"), model=PRIMARY) is None
    assert classify_exception(KeyError("x"), model=PRIMARY) is None


def test_error_message_never_contains_the_key() -> None:
    exc = api_error(400, "INVALID_ARGUMENT", f"API key not valid: {KEY}")
    err = classify_exception(exc, model=PRIMARY, secret=KEY)
    assert err is not None
    assert KEY not in str(err)
    assert "[REDACTED]" in err.message


# --- §7 table: retry / fallback behaviour through GeminiClient -------------------------------

# (outcome of the first attempt, error_class, same-model retry?, fallback-eligible?)
TABLE = [
    (RATE_MINUTE, "rate_limit_minute", True, True),
    (QUOTA_DAY, "quota_daily", False, True),
    (SERVER_503, "overloaded", False, True),
    (SERVER_500, "server_5xx", True, True),
    (READ_TIMEOUT, "timeout", True, True),
    (NOT_FOUND, "model_not_found", False, True),
    (BAD_REQUEST, "bad_request", False, False),
    (BAD_KEY, "auth_billing", False, False),
]


@pytest.mark.parametrize(("first", "kind", "retry", "fallback"), TABLE, ids=[r[1] for r in TABLE])
def test_first_failure_then_success(first: Any, kind: str, retry: bool, fallback: bool) -> None:
    client, sdk, _ = make_client([first, ok_response()])
    if not retry and not fallback:
        with pytest.raises(ProviderError) as info:
            client.generate(request())
        assert info.value.kind == kind
        assert sdk.models.models_called == [PRIMARY]  # never retried, never failed over
        assert [a.to_dict() for a in info.value.attempts] == [
            {
                "model": PRIMARY,
                "reason": "primary",
                "status": "failed",
                "error_class": kind,
                "latency_ms": 0,
            }
        ]
        return

    # With a fallback configured, every fallback-eligible error tries it before any same-model
    # retry (all of them are fallback-eligible here).
    assert fallback
    resp = client.generate(request())
    assert resp.final_json == FINAL
    assert sdk.models.models_called == [PRIMARY, FALLBACK]
    assert [(a.model, a.reason, a.status, a.error_class) for a in resp.attempts] == [
        (PRIMARY, "primary", "fallback", kind),
        (FALLBACK, "failover", "ok", None),
    ]
    assert resp.model_id == FALLBACK
    assert resp.fallback_used is True


@pytest.mark.parametrize(("first", "kind", "retry", "fallback"), TABLE, ids=[r[1] for r in TABLE])
def test_without_fallback_model(first: Any, kind: str, retry: bool, fallback: bool) -> None:
    client, sdk, _ = make_client([first, ok_response()], fallback_model=None)
    if retry:
        assert client.generate(request()).model_id == PRIMARY
        assert sdk.models.models_called == [PRIMARY, PRIMARY]
    else:
        with pytest.raises(ProviderError) as info:
            client.generate(request())
        assert info.value.kind == kind
        assert sdk.models.models_called == [PRIMARY]


@pytest.mark.parametrize("exc", [RATE_MINUTE, SERVER_500, READ_TIMEOUT], ids=str)
def test_same_model_retry_is_once_and_attempts_are_capped(exc: Any) -> None:
    # No fallback: first attempt + one same-model retry, even with budget to spare.
    client, sdk, _ = make_client([exc, exc, ok_response()], fallback_model=None, max_attempts=3)
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert sdk.models.models_called == [PRIMARY, PRIMARY]
    assert [a.status for a in info.value.attempts] == ["retry", "failed"]
    assert [a.reason for a in info.value.attempts] == ["primary", "retry"]


@pytest.mark.parametrize("exc", [RATE_MINUTE, SERVER_500, READ_TIMEOUT], ids=str)
def test_transient_error_order_is_primary_fallback_then_same_model_retry(exc: Any) -> None:
    client, sdk, _ = make_client([exc, exc, ok_response()], max_attempts=3)
    resp = client.generate(request())
    assert sdk.models.models_called == [PRIMARY, FALLBACK, FALLBACK]
    assert [(a.reason, a.status) for a in resp.attempts] == [
        ("primary", "fallback"),
        ("failover", "retry"),
        ("retry", "ok"),
    ]
    assert resp.fallback_used


@pytest.mark.parametrize("exc", [SERVER_503, SERVER_504], ids=["503", "504"])
def test_overload_goes_to_fallback_without_same_model_retry(exc: Any) -> None:
    client, sdk, sleeps = make_client([exc, ok_response()], max_attempts=3)
    resp = client.generate(request())
    assert sdk.models.models_called == [PRIMARY, FALLBACK]
    assert [(a.model, a.status, a.error_class) for a in resp.attempts] == [
        (PRIMARY, "fallback", "overloaded"),
        (FALLBACK, "ok", None),
    ]
    assert resp.model_id == FALLBACK and resp.fallback_used
    assert sleeps == []  # failover never backs off


@pytest.mark.parametrize("exc", [SERVER_503, SERVER_504], ids=["503", "504"])
def test_overload_on_every_model_is_never_retried_on_the_same_model(exc: Any) -> None:
    client, sdk, _ = make_client([exc, exc, ok_response()], max_attempts=3)
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "overloaded"
    assert info.value.fallback_used is True
    assert sdk.models.models_called == [PRIMARY, FALLBACK]
    assert [a.status for a in info.value.attempts] == ["fallback", "failed"]


def test_overload_without_fallback_fails_fast() -> None:
    client, sdk, _ = make_client([SERVER_503, ok_response()], fallback_model=None, max_attempts=3)
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "overloaded"
    assert info.value.fallback_used is False
    assert sdk.models.models_called == [PRIMARY]


def test_attempt_budget_is_per_semantic_call() -> None:
    # Each generate() is one semantic call with its own transport-attempt budget.
    client, sdk, _ = make_client([SERVER_503, ok_response(), SERVER_503, ok_response()])
    first = client.generate(request())
    second = client.generate(request(tool_mode="none"))
    assert len(first.attempts) == 2 and len(second.attempts) == 2
    assert len(sdk.models.calls) == 4


def test_backoff_is_short_and_jittered_only_for_rate_limit_and_5xx() -> None:
    for exc in (RATE_MINUTE, SERVER_500):
        client, _, sleeps = make_client([exc, ok_response()], fallback_model=None)
        client.generate(request())
        assert len(sleeps) == 1 and 0 < sleeps[0] <= MAX_BACKOFF_S

    client, _, sleeps = make_client([READ_TIMEOUT, ok_response()], fallback_model=None)
    client.generate(request())
    assert sleeps == []

    client, _, sleeps = make_client([RATE_MINUTE, ok_response()])  # failover: no backoff
    client.generate(request())
    assert sleeps == []


def test_quota_daily_disables_the_model_for_the_rest_of_the_batch() -> None:
    client, sdk, _ = make_client([QUOTA_DAY, ok_response(), ok_response()])
    client.generate(request())
    later = client.generate(request())
    assert sdk.models.models_called == [PRIMARY, FALLBACK, FALLBACK]
    assert later.model_id == FALLBACK and later.fallback_used
    assert [a.reason for a in later.attempts] == ["primary_disabled"]


def test_quota_daily_on_every_model_fails_fast() -> None:
    client, sdk, _ = make_client([QUOTA_DAY, QUOTA_DAY])
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "quota_daily"
    with pytest.raises(ProviderError) as again:
        client.generate(request())
    assert again.value.kind == "quota_daily"
    assert again.value.attempts == ()
    assert sdk.models.models_called == [PRIMARY, FALLBACK]


@pytest.mark.parametrize(
    "exc",
    [
        BAD_KEY,
        api_error(401, "UNAUTHENTICATED", "invalid credentials"),
        api_error(403, "PERMISSION_DENIED", "billing disabled"),
        api_error(400, "FAILED_PRECONDITION", "precondition"),
    ],
    ids=["400-key", "401", "403", "failed-precondition"],
)
def test_auth_billing_is_never_retried_and_latches(exc: Any) -> None:
    client, sdk, sleeps = make_client([exc, ok_response(), ok_response()], max_attempts=5)
    with pytest.raises(AuthBillingError):
        client.generate(request())
    with pytest.raises(AuthBillingError) as again:
        client.generate(request())
    assert again.value.attempts == ()
    assert sdk.models.models_called == [PRIMARY]  # one transport attempt in total
    assert sleeps == []


@pytest.mark.parametrize(
    "finish", [types.FinishReason.SAFETY, types.FinishReason.PROHIBITED_CONTENT]
)
def test_blocked_safety_is_not_retried(finish: types.FinishReason) -> None:
    client, sdk, _ = make_client([ok_response([], finish=finish), ok_response()])
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "blocked_safety"
    assert sdk.models.models_called == [PRIMARY]


def test_blocked_prompt_is_blocked_safety() -> None:
    blocked = types.GenerateContentResponse(
        prompt_feedback=types.GenerateContentResponsePromptFeedback(
            block_reason=types.BlockedReason.SAFETY
        )
    )
    client, sdk, _ = make_client([blocked, ok_response()])
    with pytest.raises(ProviderError) as info:
        client.generate(request())
    assert info.value.kind == "blocked_safety"
    assert len(sdk.models.calls) == 1


@pytest.mark.parametrize(
    "resp",
    [
        ok_response([types.Part(text="not json at all")]),
        ok_response([types.Part(text='["a list", "not an object"]')]),
        ok_response([], finish=types.FinishReason.MALFORMED_FUNCTION_CALL),
        ok_response([types.Part(text='{"answer": "trunc')], finish=types.FinishReason.MAX_TOKENS),
        types.GenerateContentResponse(candidates=[]),
    ],
    ids=["text", "json-list", "malformed-call", "truncated", "no-candidates"],
)
def test_malformed_output_is_returned_for_repair_not_retried(resp: Any) -> None:
    client, sdk, _ = make_client([resp, ok_response()])
    out = client.generate(request())
    assert out.malformed
    assert out.final_json is None and out.function_calls == ()
    assert len(sdk.models.calls) == 1
    assert [a.status for a in out.attempts] == ["ok"]


def test_unclassified_exception_propagates() -> None:
    client, _, _ = make_client([RuntimeError("programming error")])
    with pytest.raises(RuntimeError):
        client.generate(request())


# --- timeouts and the case deadline -----------------------------------------------------------


def _timing_out(seconds: float):
    def outcome(clock: Clock) -> BaseException:
        clock.t += seconds
        return httpx.ReadTimeout("timed out")

    return outcome


def test_timeout_retry_when_deadline_allows_uses_remaining_time() -> None:
    client, sdk, _ = make_client(
        [_timing_out(20.0), ok_response()], timeout_s=20.0, fallback_model=None
    )
    resp = client.generate(request(deadline=1000.0 + 32.0))
    assert [a.status for a in resp.attempts] == ["retry", "ok"]
    assert resp.attempts[0].latency_ms == 20000
    timeouts = [c["config"].http_options.timeout for c in sdk.models.calls]
    assert timeouts == [20000, 12000]  # second attempt capped by the remaining case time


def test_failover_attempt_uses_remaining_time() -> None:
    client, sdk, _ = make_client([_timing_out(20.0), ok_response()], timeout_s=20.0)
    resp = client.generate(request(deadline=1000.0 + 32.0))
    assert sdk.models.models_called == [PRIMARY, FALLBACK]
    assert [a.status for a in resp.attempts] == ["fallback", "ok"]
    timeouts = [c["config"].http_options.timeout for c in sdk.models.calls]
    assert timeouts == [20000, 12000]


def _overloaded_after(seconds: float):
    def outcome(clock: Clock) -> BaseException:
        clock.t += seconds
        return SERVER_504

    return outcome


def test_overload_failover_respects_the_case_deadline() -> None:
    # 504 after 10 s with 15 s left: 5 s remain, below the API minimum, so no fallback attempt.
    client, sdk, _ = make_client([_overloaded_after(10.0), ok_response()], max_attempts=3)
    with pytest.raises(ProviderError) as info:
        client.generate(request(deadline=1000.0 + 15.0))
    assert info.value.kind == "overloaded"
    assert [a.status for a in info.value.attempts] == ["failed"]
    assert sdk.models.models_called == [PRIMARY]

    # 25 s budget: the fallback gets the remaining 15 s, capped at the 10 s attempt timeout.
    client, sdk, _ = make_client([_overloaded_after(10.0), ok_response()], max_attempts=3)
    resp = client.generate(request(deadline=1000.0 + 25.0))
    assert sdk.models.models_called == [PRIMARY, FALLBACK]
    assert [c["config"].http_options.timeout for c in sdk.models.calls] == [10000, 10000]
    assert resp.model_id == FALLBACK


def test_timeout_not_retried_when_deadline_does_not_allow() -> None:
    client, sdk, _ = make_client([_timing_out(10.0), ok_response()])
    with pytest.raises(ProviderError) as info:
        client.generate(request(deadline=1000.0 + 10.2))
    assert info.value.kind == "timeout"
    assert [a.status for a in info.value.attempts] == ["failed"]
    assert len(sdk.models.calls) == 1


def test_remaining_time_below_api_minimum_makes_no_transport_call() -> None:
    client, sdk, _ = make_client([_timing_out(10.0), ok_response()])
    with pytest.raises(ProviderError) as info:
        client.generate(request(deadline=1000.0 + 15.0))  # 5 s left: too short for the API
    assert info.value.kind == "timeout"
    assert [a.status for a in info.value.attempts] == ["failed"]  # no second attempt started
    assert len(sdk.models.calls) == 1


@pytest.mark.parametrize("configured", [0.5, 8.0, 9.99])
def test_sdk_timeout_is_never_below_the_api_minimum(configured: float) -> None:
    client, sdk, _ = make_client([ok_response(), ok_response()], timeout_s=configured)
    client.generate(request())
    client.generate(request(deadline=1000.0 + 60.0))
    for call in sdk.models.calls:
        assert call["config"].http_options.timeout >= GEMINI_MIN_TIMEOUT_S * 1000
    real = GeminiClient(settings(timeout_s=configured))  # constructs the SDK client; no request
    assert real._client._api_client._http_options.timeout >= GEMINI_MIN_TIMEOUT_S * 1000


def test_expired_deadline_makes_no_attempt() -> None:
    client, sdk, _ = make_client([ok_response()])
    with pytest.raises(ProviderError) as info:
        client.generate(request(deadline=1000.0))
    assert info.value.kind == "timeout"
    assert sdk.models.calls == []


# --- primary health breaker (batch-scoped cooldown) -------------------------------------------


def _engage_cooldown(client: GeminiClient) -> None:
    for _ in range(PRIMARY_BREAKER_THRESHOLD):
        client.generate(request())  # primary fails, the fallback answers
    assert client.runner.cooldown_left == PRIMARY_COOLDOWN_CALLS


def _outcomes(first_failures: list[Any], n_ok: int) -> list[Any]:
    out: list[Any] = []
    for exc in first_failures:
        out += [exc, ok_response()]
    return out + [ok_response() for _ in range(n_ok)]


@pytest.mark.parametrize("exc", [SERVER_503, SERVER_504, READ_TIMEOUT], ids=str)
def test_cooldown_engages_after_consecutive_primary_overloads(exc: Any) -> None:
    client, sdk, _ = make_client(_outcomes([exc, exc], 1))
    _engage_cooldown(client)
    resp = client.generate(request())
    assert sdk.models.models_called[-1] == FALLBACK
    assert [(a.model, a.reason) for a in resp.attempts] == [(FALLBACK, "primary_cooldown")]
    assert resp.fallback_used and resp.model_id == FALLBACK
    assert client.runner.cooldowns_started == 1


def test_cooldown_needs_consecutive_failures() -> None:
    outcomes = [SERVER_503, ok_response(), ok_response(), SERVER_503, ok_response(), ok_response()]
    client, sdk, _ = make_client(outcomes)
    for _ in range(3):
        client.generate(request())  # overload, success on the primary, overload
    assert client.runner.cooldown_left == 0
    assert client.generate(request()).attempts[0].model == PRIMARY


def test_other_errors_do_not_engage_the_cooldown() -> None:
    client, _, _ = make_client(_outcomes([SERVER_500, RATE_MINUTE, SERVER_500], 1))
    for _ in range(3):
        client.generate(request())
    assert client.runner.cooldown_left == 0 and client.runner.cooldowns_started == 0


def test_cooldown_releases_after_the_window_and_probes_the_primary() -> None:
    client, sdk, _ = make_client(_outcomes([SERVER_503, SERVER_503], PRIMARY_COOLDOWN_CALLS + 2))
    _engage_cooldown(client)
    for _ in range(PRIMARY_COOLDOWN_CALLS):
        resp = client.generate(request())
        assert [(a.model, a.reason) for a in resp.attempts] == [(FALLBACK, "primary_cooldown")]
    probe = client.generate(request())
    assert [(a.model, a.reason, a.status) for a in probe.attempts] == [
        (PRIMARY, "primary_probe", "ok")
    ]
    assert not probe.fallback_used
    after = client.generate(request())
    assert [(a.model, a.reason) for a in after.attempts] == [(PRIMARY, "primary")]
    assert client.runner.cooldowns_started == 1


def test_failed_probe_reopens_the_cooldown_at_once() -> None:
    client, sdk, _ = make_client(_outcomes([SERVER_503, SERVER_503], PRIMARY_COOLDOWN_CALLS))
    _engage_cooldown(client)
    for _ in range(PRIMARY_COOLDOWN_CALLS):
        client.generate(request())
    sdk.models.outcomes = [SERVER_503, ok_response(), ok_response()]
    probe = client.generate(request())
    assert [(a.model, a.reason, a.status) for a in probe.attempts] == [
        (PRIMARY, "primary_probe", "fallback"),
        (FALLBACK, "failover", "ok"),
    ]
    assert client.runner.cooldown_left == PRIMARY_COOLDOWN_CALLS
    assert client.runner.cooldowns_started == 2
    assert client.generate(request()).attempts[0].reason == "primary_cooldown"


def test_cooldown_keeps_the_primary_as_second_choice() -> None:
    client, sdk, _ = make_client(
        _outcomes([SERVER_503, SERVER_503], 0) + [SERVER_503, ok_response()]
    )
    _engage_cooldown(client)
    resp = client.generate(request())
    assert sdk.models.models_called[-2:] == [FALLBACK, PRIMARY]
    assert [(a.model, a.reason, a.status) for a in resp.attempts] == [
        (FALLBACK, "primary_cooldown", "fallback"),
        (PRIMARY, "failover", "ok"),
    ]
    assert resp.fallback_used and resp.model_id == PRIMARY


def test_cooldown_never_switches_credential() -> None:
    client, sdk, _ = make_client(_outcomes([SERVER_503, SERVER_503], 1))
    sdk_client = client._client
    _engage_cooldown(client)
    client.generate(request())
    assert client._client is sdk_client  # one SDK client (one key) for the whole batch
    normal, cooled = sdk.models.calls[0], sdk.models.calls[-1]
    assert (normal["model"], cooled["model"]) == (PRIMARY, FALLBACK)
    assert normal["config"].model_dump() == cooled["config"].model_dump()  # only the model differs

    real = GeminiClient(settings())  # the key is bound once, at construction
    real.runner.cooldown_left = PRIMARY_COOLDOWN_CALLS
    assert real._client._api_client.api_key == KEY


def test_no_cooldown_without_a_fallback_model() -> None:
    client, sdk, _ = make_client(
        [SERVER_503, SERVER_503, SERVER_503, ok_response()], fallback_model=None
    )
    for _ in range(3):
        with pytest.raises(ProviderError):
            client.generate(request())
    assert client.runner.cooldown_left == 0
    assert client.generate(request()).attempts[0].reason == "primary"
    assert set(sdk.models.models_called) == {PRIMARY}


def test_auth_billing_during_cooldown_latches_without_trying_the_primary() -> None:
    client, sdk, sleeps = make_client(
        _outcomes([SERVER_503, SERVER_503], 0) + [BAD_KEY], max_attempts=3
    )
    _engage_cooldown(client)
    with pytest.raises(AuthBillingError) as info:
        client.generate(request())
    assert [(a.model, a.status) for a in info.value.attempts] == [(FALLBACK, "failed")]
    with pytest.raises(AuthBillingError) as again:
        client.generate(request())
    assert again.value.attempts == ()
    assert sdk.models.models_called[-1] == FALLBACK and len(sdk.models.calls) == 5
    assert sleeps == []


def test_breaker_state_is_per_client_instance() -> None:
    first, _, _ = make_client(_outcomes([SERVER_503, SERVER_503], 0))
    _engage_cooldown(first)
    second, sdk, _ = make_client([ok_response()])
    assert second.runner.cooldown_left == 0
    assert second.generate(request()).attempts[0].model == PRIMARY


# --- request configuration -------------------------------------------------------------------


def test_config_auto_mode_with_tools_schema_and_thinking() -> None:
    client, sdk, _ = make_client([ok_response()], thinking_level="minimal", max_output_tokens=600)
    client.generate(request())
    config: types.GenerateContentConfig = sdk.models.calls[0]["config"]
    assert config.automatic_function_calling.disable is True
    assert config.http_options.retry_options.attempts == 1
    assert config.http_options.timeout == 10000
    assert config.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.AUTO
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert config.max_output_tokens == 600
    assert config.candidate_count == 1
    assert config.system_instruction == request().system
    assert config.response_mime_type == "application/json"

    decl = config.tools[0].function_declarations[0]
    assert decl.name == "get_my_orders"
    assert "user_id" not in (decl.parameters.properties or {})
    assert decl.parameters.properties["order_id"].pattern == r"^ord_\d{1,6}$"

    schema = config.response_schema
    assert schema.required == ["answer", "escalation_reason", "policy_applied", "cited_policies"]
    assert schema.property_ordering == schema.required
    assert "none" in schema.properties["escalation_reason"].enum
    assert schema.properties["answer"].max_length == 1200


def test_config_none_mode_and_no_tools() -> None:
    client, sdk, _ = make_client([ok_response(), ok_response()])
    client.generate(request(tool_mode="none", max_output_tokens=123))
    config = sdk.models.calls[0]["config"]
    assert config.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.NONE
    assert config.tools  # declarations stay present so the replayed tool turn stays valid
    assert config.max_output_tokens == 123

    client.generate(request(tools=()))
    bare = sdk.models.calls[1]["config"]
    assert bare.tools is None and bare.tool_config is None


def test_config_thinking_level_follows_settings() -> None:
    client, sdk, _ = make_client([ok_response()], thinking_level="low")
    client.generate(request())
    assert sdk.models.calls[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_fallback_uses_same_sdk_client_and_only_changes_the_model() -> None:
    client, sdk, _ = make_client([NOT_FOUND, ok_response()])
    client.generate(request())
    first, second = sdk.models.calls
    assert (first["model"], second["model"]) == (PRIMARY, FALLBACK)
    assert first["contents"] is second["contents"]
    assert first["config"].model_dump() == second["config"].model_dump()


def test_real_sdk_client_uses_only_the_settings_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "inherited-gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "inherited-google-key")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", "https://example.invalid/")
    client = GeminiClient(settings())  # constructs the SDK client; makes no request
    api = client._client._api_client
    assert api.api_key == KEY
    assert api.vertexai is False
    assert api._http_options.base_url == GEMINI_BASE_URL
    assert api._http_options.retry_options.attempts == 1
    assert api._http_options.timeout == 10000


def test_missing_key_is_a_config_error() -> None:
    from support_agent.config import ConfigError

    with pytest.raises(ConfigError):
        GeminiClient(settings(api_key=None), client=StubSDK([]))


# --- normalization ----------------------------------------------------------------------------


def test_function_call_turn_is_preserved_unchanged() -> None:
    call_part = types.Part(
        function_call=types.FunctionCall(
            name="get_my_orders", args={"order_id": "ord_1"}, id="call_1"
        ),
        thought_signature=b"opaque-signature",
    )
    resp = ok_response([call_part])
    client, sdk, _ = make_client([resp, ok_response()])
    out = client.generate(request())
    assert out.final_json is None and not out.malformed
    assert [(c.name, c.args, c.call_id) for c in out.function_calls] == [
        ("get_my_orders", {"order_id": "ord_1"}, "call_1")
    ]
    assert out.raw_model_turn is resp.candidates[0].content

    # Call #2 replays the raw turn untouched (thought signature intact) + the function response.
    history = (
        UserMessage("q"),
        ModelTurn(out.raw_model_turn),
        ToolResult("get_my_orders", {"status": "not_found", "orders": []}, "call_1"),
    )
    client.generate(request(contents=history, tool_mode="none"))
    sent = sdk.models.calls[1]["contents"]
    assert sent[1] is out.raw_model_turn
    assert sent[1].parts[0].thought_signature == b"opaque-signature"
    assert sent[2].role == "user"
    fr = sent[2].parts[0].function_response
    assert (fr.name, fr.id, fr.response) == ("get_my_orders", "call_1", history[2].response)


def test_consecutive_tool_results_share_one_user_turn() -> None:
    contents = to_contents(
        [UserMessage("q"), ToolResult("a", {"x": 1}, "c1"), ToolResult("b", {"y": 2}, "c2")]
    )
    assert len(contents) == 2
    assert [p.function_response.name for p in contents[1].parts] == ["a", "b"]


def test_model_turn_must_be_a_gemini_content() -> None:
    with pytest.raises(TypeError):
        to_contents([ModelTurn({"role": "model"})])


def test_thought_parts_are_not_answer_text() -> None:
    resp = ok_response(
        [types.Part(text="internal musing", thought=True), types.Part(text=json.dumps(FINAL))]
    )
    client, _, _ = make_client([resp])
    out = client.generate(request())
    assert out.final_json == FINAL
    FinalAnswer.model_validate(out.final_json)


def test_usage_normalization_is_none_safe() -> None:
    assert to_usage(None).to_dict() == {"input": 0, "output": 0, "cached": 0, "thoughts": 0}
    md = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=3300,
        candidates_token_count=80,
        cached_content_token_count=2048,
        thoughts_token_count=None,
    )
    assert to_usage(md).to_dict() == {"input": 3300, "output": 80, "cached": 2048, "thoughts": 0}

    client, _, _ = make_client([ok_response(usage=md)])
    out = client.generate(request())
    assert out.usage.cached == 2048 and out.usage.thoughts == 0
    assert out.model_id == PRIMARY and out.finish_reason == "STOP"
