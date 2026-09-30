"""GroqCloud adapter over the OpenAI-compatible Chat Completions API (P-008, OD-26; architecture
§3.4, §7; OWN-02, SEC-07).

- Transport: plain ``httpx`` to ``https://api.groq.com/openai/v1/chat/completions`` (no vendor
  SDK). The key comes only from ``Settings.api_key`` (``GROQ_API_KEY``, AR-09) and is sent only as
  the ``Authorization: Bearer`` header of that pinned base URL; ``trust_env=False`` so no inherited
  proxy/netrc/cert variable can change where requests go. Redirects are not followed.
- Structured output: Groq cannot combine ``response_format`` json_schema with ``tools``, so the
  final answer is a function tool, ``submit_answer``, whose parameters are the ``FinalAnswer``
  JSON schema. Tool mode ``auto`` → tools ``[get_my_orders, submit_answer]`` with
  ``tool_choice="required"``; tool mode ``none`` → tools ``[submit_answer]`` with that function
  forced, so another lookup is structurally impossible. ``parallel_tool_calls`` is off.
- Normalization: a ``submit_answer`` call becomes ``final_json``; any other call becomes a
  ``FunctionCall`` (the agent executes only registered tools and rejects the rest); a turn with
  unparseable/non-object arguments, or with no tool call at all, is malformed (repair path).
  A 400 ``tool_use_failed`` (the model produced an invalid tool call, rejected by Groq's
  server-side validation) is also a malformed attempt, not a provider error.
- History: OpenAI chat format. ``system`` message = the static prefix; ``raw_model_turn`` is the
  assistant message dict exactly as returned and is replayed unchanged; tool results become
  ``tool`` messages with their ``tool_call_id``. A replayed call that got no result (a
  ``submit_answer`` before a repair, a malformed call) gets a data-free acknowledgement so the
  history stays well-formed.
- Usage: ``prompt_tokens`` → input, ``completion_tokens`` (reasoning included) → output,
  ``prompt_tokens_details.cached_tokens`` → cached, ``completion_tokens_details.reasoning_tokens``
  → thoughts; missing counts are 0.
- Pacing (eval runs on the free plan): ``TokenPacer`` keeps a per-model rolling-minute token
  window (``GROQ_TPM_BUDGET``), an optional minimum interval between call starts
  (``GROQ_MIN_CALL_INTERVAL_S``) and the ``retry-after`` of a per-minute 429. It is operational
  state of this per-batch client (timestamps and token counts only). A wait that cannot end
  before the case deadline is not taken: the attempt fails as ``rate_limit_minute`` without being
  sent, so the fallback model (a separate quota bucket) is tried.

Error classification (``classify_response``), per the §7 table:

- 401/403 → ``auth_billing``; 404 → ``model_not_found``; 408 → ``timeout``.
- 413 → ``bad_request`` (the request exceeds the body size or the per-minute token limit; logged).
- 429 → ``quota_daily`` when the daily request budget is spent (``x-ratelimit-remaining-requests``
  is ``0``: Groq's request headers are per day) or the message names a per-day limit (TPD/RPD);
  otherwise ``rate_limit_minute``, honouring ``retry-after`` before the next attempt on that model.
- Other 4xx → ``bad_request``; 498/503/504 → ``overloaded``; other 5xx → ``server_5xx``.
- Client timeouts → ``timeout``; other transport failures or an unreadable 200 body →
  ``server_5xx``.
- ``finish_reason == "content_filter"`` → ``blocked_safety``.

Error messages are truncated and scrubbed of the key and organisation IDs before they leave this
module (SEC-13); request/response bodies are never logged.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from support_agent.config import GROQ_PACING_WINDOW_S, ConfigError, Settings
from support_agent.llm.base import (
    MIN_ATTEMPT_BUDGET_S,
    AttemptOutput,
    AttemptRunner,
    FunctionCall,
    LLMRequest,
    LLMResponse,
    Message,
    ModelTurn,
    ProviderError,
    ToolResult,
    Usage,
    UserMessage,
    provider_error,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
CHAT_COMPLETIONS_PATH = "/chat/completions"
SUBMIT_ANSWER = "submit_answer"
SUBMIT_ANSWER_DESCRIPTION = (
    "Submit the final answer to the shopper. The arguments are the complete final answer, "
    "the JSON object described in the instructions. Call it exactly once, when ready to answer."
)
# Protocol-only replies for replayed calls that got no result; they carry no data.
_SUBMITTED_ACK = {"status": "received"}
_NOT_EXECUTED_ACK = {"status": "not_executed"}

DEFAULT_CHARS_PER_TOKEN = 4.0
_MIN_CHARS_PER_TOKEN, _MAX_CHARS_PER_TOKEN = 1.0, 8.0
_OVERLOAD_CODES = frozenset({498, 503, 504})
_DAILY_HINT_RE = re.compile(
    r"per[\s_-]?day|daily|\b(?:TPD|RPD)\b|(?:tokens|requests)\s+per\s+day", re.I
)
_ORG_ID_RE = re.compile(r"\borg_[A-Za-z0-9]+")
_MAX_MESSAGE_CHARS = 300
# Errors for which Groq did not process the request: its pacing estimate is released.
_NOT_PROCESSED = frozenset(
    {
        "rate_limit_minute",
        "quota_daily",
        "bad_request",
        "auth_billing",
        "model_not_found",
        "overloaded",
        "server_5xx",
    }
)

logger = logging.getLogger(__name__)


class GroqClient:
    """``LLMClient`` over GroqCloud. One instance per batch (it holds breaker and pacing state)."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if settings.api_key is None:
            raise ConfigError(f"{settings.credential_env_var} is required for the Groq provider")
        self._settings = settings
        self._secret = settings.api_key.reveal()
        self._http = httpx.Client(
            base_url=GROQ_BASE_URL,
            headers={"Authorization": f"Bearer {self._secret}"},
            timeout=settings.timeout_s,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        )
        self.runner = AttemptRunner(
            settings.primary_model,
            settings.fallback_model,
            max_attempts=settings.max_attempts,
            timeout_s=settings.timeout_s,
            sleep=sleep,
            clock=clock,
        )
        self.pacer = TokenPacer(
            tpm_budget=settings.tpm_budget,
            min_interval_s=settings.min_call_interval_s,
            min_attempt_s=self.runner.min_attempt_s,
            sleep=sleep,
            clock=clock,
        )

    def __repr__(self) -> str:
        return f"GroqClient(models={self.runner.models!r})"

    def close(self) -> None:
        self._http.close()

    def generate(self, req: LLMRequest) -> LLMResponse:
        messages = to_messages(req.system, req.contents)
        max_tokens = req.max_output_tokens or self._settings.max_output_tokens
        request_chars = _request_chars(messages, req)
        estimate = self.pacer.estimate(request_chars, max_tokens)
        tickets: dict[str, _Ticket] = {}

        def pace(model: str, deadline: float | None) -> float:
            waited, tickets[model] = self.pacer.acquire(model, estimate, deadline)
            return waited

        def attempt(model: str, timeout_s: float) -> AttemptOutput:
            ticket = tickets.pop(model)
            body = self.build_body(req, model, messages, max_tokens)
            try:
                response = self._http.post(CHAT_COMPLETIONS_PATH, json=body, timeout=timeout_s)
            except httpx.TimeoutException as exc:
                raise ProviderError(
                    "timeout", f"client timeout ({type(exc).__name__})", model=model
                ) from None
            except httpx.TransportError as exc:
                self.pacer.release(ticket)
                raise ProviderError(
                    "server_5xx", f"transport failure ({type(exc).__name__})", model=model
                ) from None

            if response.status_code != 200:
                if _is_tool_use_failed(response):
                    # The model's tool call failed Groq's validation: a malformed attempt.
                    return AttemptOutput(finish_reason="tool_use_failed")
                err = classify_response(response, model=model, secret=self._secret)
                if err.kind in _NOT_PROCESSED:
                    self.pacer.release(ticket)
                if err.kind == "rate_limit_minute":
                    self.pacer.block(model, _retry_after_s(response))
                if response.status_code == 413:
                    logger.warning(
                        "Groq rejected a request as too large (HTTP 413) for model %s: "
                        "~%d estimated tokens against GROQ_TPM_BUDGET=%d",
                        model,
                        estimate,
                        self._settings.tpm_budget,
                    )
                raise err

            try:
                data = response.json()
            except ValueError:
                self.pacer.release(ticket)
                raise ProviderError(
                    "server_5xx", "HTTP 200 with a body that is not JSON", model=model
                ) from None
            if not isinstance(data, Mapping):
                self.pacer.release(ticket)
                raise ProviderError("server_5xx", "HTTP 200 with a non-object body", model=model)
            out = to_attempt_output(data, model=model)
            self.pacer.settle(ticket, out.usage, request_chars)
            return out

        return self.runner.run(attempt, deadline=req.deadline, pace=pace)

    def build_body(
        self,
        req: LLMRequest,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
            "reasoning_effort": self._settings.reasoning_effort,
            # Reasoning text is not needed, and keeps replayed assistant turns plain.
            "include_reasoning": False,
        }
        tools, tool_choice = tools_for(req)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice
            body["parallel_tool_calls"] = False
        return body


# --- pacing -----------------------------------------------------------------------------------


@dataclass
class _Ticket:
    """One call's entry in a model's rolling token window."""

    model: str
    started: float
    tokens: int


class TokenPacer:
    """Client-side pacing per model (GroqCloud free plan limits are per model).

    Before an attempt, waits until (a) the model's rolling-minute token window has room for the
    call's estimated tokens under ``tpm_budget`` (a call larger than the whole budget waits for an
    empty window), (b) ``min_interval_s`` has passed since the model's previous call started and
    (c) any ``retry-after`` from a per-minute 429 has elapsed. The estimate is
    ``request chars / chars-per-token + max_completion_tokens``, with chars-per-token starting at 4
    and recalibrated from each reported ``prompt_tokens``; once a response reports usage, the
    call's window entry becomes the reported uncached input + output. ``tpm_budget=0`` and
    ``min_interval_s=0`` disable (a) and (b)."""

    def __init__(
        self,
        *,
        tpm_budget: int,
        min_interval_s: float,
        min_attempt_s: float = MIN_ATTEMPT_BUDGET_S,
        window_s: float = GROQ_PACING_WINDOW_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.tpm_budget = tpm_budget
        self.min_interval_s = min_interval_s
        self.min_attempt_s = min_attempt_s
        self.window_s = window_s
        self.chars_per_token = DEFAULT_CHARS_PER_TOKEN
        self._sleep = sleep
        self._clock = clock
        self._windows: dict[str, deque[_Ticket]] = {}
        self._last_start: dict[str, float] = {}
        self._not_before: dict[str, float] = {}

    def estimate(self, request_chars: int, max_completion_tokens: int) -> int:
        return math.ceil(request_chars / self.chars_per_token) + max_completion_tokens

    def used(self, model: str) -> int:
        """Tokens in ``model``'s current rolling window."""
        window = self._window(model, self._clock())
        return sum(t.tokens for t in window)

    def acquire(self, model: str, tokens: int, deadline: float | None) -> tuple[float, _Ticket]:
        """Wait until the call may start; returns the seconds waited and its window entry.
        Raises ``rate_limit_minute`` (without waiting) if the wait would pass the deadline."""
        now = self._clock()
        ready = self._ready_at(model, tokens, now)
        waited = 0.0
        if ready > now:
            if deadline is not None and ready > deadline - self.min_attempt_s:
                raise ProviderError(
                    "rate_limit_minute",
                    f"client-side pacing needs {ready - now:.1f} s before the next call, "
                    f"beyond the case deadline; not sent",
                    model=model,
                )
            self._sleep(ready - now)
            waited = self._clock() - now
        started = self._clock()
        ticket = _Ticket(model, started, tokens)
        self._windows.setdefault(model, deque()).append(ticket)
        self._last_start[model] = started
        return waited, ticket

    def settle(self, ticket: _Ticket, usage: Usage, request_chars: int) -> None:
        """Replace the estimate with reported usage (cached input does not count toward TPM)."""
        if usage.input <= 0 and usage.output <= 0:
            return
        ticket.tokens = max(0, usage.input - usage.cached) + usage.output
        if usage.input > 0 and request_chars > 0:
            ratio = request_chars / usage.input
            self.chars_per_token = min(max(ratio, _MIN_CHARS_PER_TOKEN), _MAX_CHARS_PER_TOKEN)

    def release(self, ticket: _Ticket) -> None:
        """Drop the entry of a request Groq did not process."""
        window = self._windows.get(ticket.model)
        if window is not None and ticket in window:
            window.remove(ticket)

    def block(self, model: str, seconds: float | None) -> None:
        """Honour a 429 ``retry-after`` before the next call to ``model``."""
        if seconds is not None and seconds > 0:
            until = self._clock() + seconds
            self._not_before[model] = max(self._not_before.get(model, until), until)

    def _ready_at(self, model: str, tokens: int, now: float) -> float:
        ready = max(now, self._not_before.get(model, now))
        if self.min_interval_s > 0 and model in self._last_start:
            ready = max(ready, self._last_start[model] + self.min_interval_s)
        if self.tpm_budget > 0:
            window = self._window(model, now)
            used = sum(t.tokens for t in window)
            for entry in window:  # oldest first: wait for entries to leave the window
                if used + tokens <= self.tpm_budget:
                    break
                used -= entry.tokens
                ready = max(ready, entry.started + self.window_s)
        return ready

    def _window(self, model: str, now: float) -> deque[_Ticket]:
        window = self._windows.setdefault(model, deque())
        while window and window[0].started + self.window_s <= now:
            window.popleft()
        return window


# --- request conversion -----------------------------------------------------------------------


def tools_for(req: LLMRequest) -> tuple[list[dict[str, Any]], Any]:
    """OpenAI-format tools and ``tool_choice`` for the request's tool mode (see module doc)."""
    if req.response_schema is None:
        tools = [to_tool(d) for d in req.tools]
        return tools, ("auto" if req.tool_mode == "auto" else "none")
    submit = submit_answer_tool(req.response_schema)
    if req.tool_mode == "auto":
        return [*(to_tool(d) for d in req.tools), submit], "required"
    return [submit], {"type": "function", "function": {"name": SUBMIT_ANSWER}}


def to_tool(declaration: Mapping[str, Any]) -> dict[str, Any]:
    """A plain JSON-schema declaration (``tools.py`` format) → an OpenAI function tool."""
    function: dict[str, Any] = {"name": declaration["name"]}
    if declaration.get("description"):
        function["description"] = declaration["description"]
    function["parameters"] = dict(declaration.get("parameters") or {"type": "object"})
    return {"type": "function", "function": function}


def submit_answer_tool(schema: type[BaseModel]) -> dict[str, Any]:
    """The ``submit_answer`` function tool; its parameters are the answer's JSON schema."""
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_ANSWER,
            "description": SUBMIT_ANSWER_DESCRIPTION,
            "parameters": schema.model_json_schema(),
        },
    }


def to_messages(system: str, contents: Sequence[Message]) -> list[dict[str, Any]]:
    """Normalized history → OpenAI chat messages. Model turns pass through untouched; every
    tool call of a replayed turn is answered (by its ``ToolResult`` or a data-free
    acknowledgement) before the next non-tool message."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    pending: dict[str, str] = {}  # tool_call_id -> name, calls of the last turn not yet answered
    for msg in contents:
        if isinstance(msg, UserMessage):
            _acknowledge(pending, messages)
            messages.append({"role": "user", "content": msg.text})
        elif isinstance(msg, ModelTurn):
            if not isinstance(msg.raw, Mapping) or msg.raw.get("role") != "assistant":
                raise TypeError("ModelTurn.raw must be the assistant message returned by Groq")
            _acknowledge(pending, messages)
            messages.append(dict(msg.raw))  # same content, as returned
            pending = {
                str(tc.get("id")): str((tc.get("function") or {}).get("name") or "")
                for tc in msg.raw.get("tool_calls") or []
                if isinstance(tc, Mapping)
            }
        elif isinstance(msg, ToolResult):
            call_id = _match_call(msg, pending)
            pending.pop(call_id, None)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(dict(msg.response), ensure_ascii=False),
                }
            )
        else:
            raise TypeError(f"unsupported message type {type(msg).__name__}")
    _acknowledge(pending, messages)
    return messages


def _match_call(result: ToolResult, pending: Mapping[str, str]) -> str:
    if result.call_id is not None:
        return result.call_id
    for call_id, name in pending.items():
        if name == result.name:
            return call_id
    raise ValueError(f"tool result for {result.name!r} has no matching tool call")


def _acknowledge(pending: dict[str, str], messages: list[dict[str, Any]]) -> None:
    for call_id, name in pending.items():
        ack = _SUBMITTED_ACK if name == SUBMIT_ANSWER else _NOT_EXECUTED_ACK
        messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(ack)})
    pending.clear()


def _request_chars(messages: Sequence[Mapping[str, Any]], req: LLMRequest) -> int:
    tools, _ = tools_for(req)
    return len(json.dumps(list(messages), ensure_ascii=False)) + len(
        json.dumps(tools, ensure_ascii=False)
    )


# --- response normalization -----------------------------------------------------------------


def to_attempt_output(data: Mapping[str, Any], *, model: str) -> AttemptOutput:
    """One chat-completion body → normalized output; raises ``blocked_safety`` if filtered."""
    usage = to_usage(data.get("usage"))
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return AttemptOutput(usage=usage)
    choice = choices[0]
    finish = choice.get("finish_reason")
    finish = str(finish) if finish is not None else None
    if finish == "content_filter":
        raise ProviderError("blocked_safety", "finish_reason=content_filter", model=model)
    message = choice.get("message")
    if not isinstance(message, Mapping):
        return AttemptOutput(usage=usage, finish_reason=finish)
    content = message.get("content")
    text = content if isinstance(content, str) else ""

    calls: list[FunctionCall] = []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") if isinstance(tool_call, Mapping) else None
        if not isinstance(function, Mapping):
            function = {"arguments": None, "invalid": True}
        args = None if function.get("invalid") else _parse_args(function.get("arguments"))
        if args is None:  # unparseable or non-object arguments: the whole turn is malformed
            return AttemptOutput(
                text=text, raw_model_turn=message, usage=usage, finish_reason=finish
            )
        name = function.get("name")
        call_id = tool_call.get("id")
        calls.append(
            FunctionCall(
                name=name if isinstance(name, str) else "",
                args=args,
                call_id=call_id if isinstance(call_id, str) else None,
            )
        )

    final_json: dict[str, Any] | None = None
    if calls and all(c.name == SUBMIT_ANSWER for c in calls):
        final_json, calls = calls[0].args, []
    # Otherwise every call (a premature submit_answer included) goes to the agent, which runs
    # only a registered tool and answers the rest with a rejection, keeping calls and replies
    # paired.
    return AttemptOutput(
        function_calls=tuple(calls),
        final_json=final_json,
        text=text,
        raw_model_turn=message,
        usage=usage,
        finish_reason=finish,
    )


def _parse_args(arguments: Any) -> dict[str, Any] | None:
    if arguments is None or (isinstance(arguments, str) and not arguments.strip()):
        return {}
    if isinstance(arguments, Mapping):
        return dict(arguments)
    if not isinstance(arguments, str):
        return None
    try:
        value = json.loads(arguments)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def to_usage(usage: Any) -> Usage:
    """Token usage; every missing count (``None``) becomes 0."""
    if not isinstance(usage, Mapping):
        return Usage()
    prompt_details = usage.get("prompt_tokens_details")
    completion_details = usage.get("completion_tokens_details")
    return Usage(
        input=_count(usage.get("prompt_tokens")),
        output=_count(usage.get("completion_tokens")),
        cached=_count(
            prompt_details.get("cached_tokens") if isinstance(prompt_details, Mapping) else None
        ),
        thoughts=_count(
            completion_details.get("reasoning_tokens")
            if isinstance(completion_details, Mapping)
            else None
        ),
    )


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


# --- error classification -------------------------------------------------------------------


def classify_response(
    response: httpx.Response, *, model: str | None = None, secret: str | None = None
) -> ProviderError:
    """Map a non-200 response to a ``ProviderError`` (see module doc)."""
    code = response.status_code
    error_type, error_message = _error_fields(response)
    message = f"HTTP {code} {error_type}: {error_message}"
    if code in (401, 403):
        kind = "auth_billing"
    elif code == 404:
        kind = "model_not_found"
    elif code == 408:
        kind = "timeout"
    elif code == 413:
        kind = "bad_request"
        message = f"request too large (body or per-minute token limit); {message}"
    elif code == 429:
        kind = "quota_daily" if _is_daily_limit(response, error_message) else "rate_limit_minute"
    elif code in _OVERLOAD_CODES:  # before the 4xx range: 498 is a capacity signal
        kind = "overloaded"
    elif 400 <= code < 500:
        kind = "bad_request"
    else:
        kind = "server_5xx"
    return provider_error(kind, _sanitize(message, secret), model=model)


def _is_daily_limit(response: httpx.Response, error_message: str) -> bool:
    # Groq's x-ratelimit-*-requests headers describe the per-day request budget (RPD).
    if response.headers.get("x-ratelimit-remaining-requests", "").strip() == "0":
        return True
    return bool(_DAILY_HINT_RE.search(error_message))


def _is_tool_use_failed(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    error = _error_object(response)
    return error.get("code") == "tool_use_failed"


def _error_object(response: httpx.Response) -> Mapping[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    error = body.get("error") if isinstance(body, Mapping) else None
    return error if isinstance(error, Mapping) else {}


def _error_fields(response: httpx.Response) -> tuple[str, str]:
    error = _error_object(response)
    error_type = error.get("type") or error.get("code") or ""
    error_message = error.get("message") or ""
    return str(error_type), str(error_message)


def _retry_after_s(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) and value > 0 else None


def _sanitize(message: str, secret: str | None) -> str:
    if secret:
        message = message.replace(secret, "[REDACTED]")
    message = _ORG_ID_RE.sub("org_[REDACTED]", message)
    message = " ".join(message.split())
    return message[:_MAX_MESSAGE_CHARS]
