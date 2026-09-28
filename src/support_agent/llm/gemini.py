"""``google-genai`` adapter (architecture §3.4, §7; OWN-02, OWN-06, SEC-07).

- Credential: the key comes only from ``Settings.api_key`` and is passed explicitly to
  ``genai.Client(api_key=...)``; ``vertexai=False`` and ``base_url`` are pinned too, so no
  inherited env var (``GEMINI_API_KEY``, ``GOOGLE_GENAI_USE_VERTEXAI``, ``GOOGLE_GEMINI_BASE_URL``)
  can change which key is used or where it is sent (AR-09).
- SDK retries are off (``HttpRetryOptions(attempts=1)``); ``AttemptRunner`` owns retry/fallback.
  Automatic function calling is disabled: the agent loop executes every tool call itself.
- Tool mode ``auto``/``none`` → ``FunctionCallingConfig``; the response schema, tool parameters
  and thinking level are sent on every attempt; the per-attempt timeout is
  ``min(LLM_TIMEOUT_S, time left before the case deadline)``.
- ``raw_model_turn`` is ``candidate.content`` exactly as returned, so replaying it keeps
  Gemini 3 thought signatures intact.
- Fallback changes only the model ID; credential and project stay the same (OD-16).

Error classification (``classify_exception``), per the §7 table:

- 401/403 or status ``UNAUTHENTICATED``/``PERMISSION_DENIED``/``FAILED_PRECONDITION``, or a 400
  whose message/details mention the API key or billing → ``auth_billing``.
- 404 → ``model_not_found``; 408 → ``timeout``; other 4xx → ``bad_request``; 5xx → ``server_5xx``.
- 429 heuristic: ``quota_daily`` if the error message or details (``QuotaFailure`` quota id/
  metric) name a per-day quota (``PerDay``, "per day", "daily"), or the quota value is 0
  ("limit: 0": the tier has no quota for the model, so waiting cannot help); otherwise
  ``rate_limit_minute`` (per-minute quota ids, or no hint at all). The generic free-tier text
  "check your plan and billing details" appears on both and is deliberately not a signal.
- Client-side timeouts (``httpx.TimeoutException``, ``TimeoutError``) → ``timeout``; other
  transport failures (connect/reset) → ``server_5xx``: transient, retry- and fallback-eligible.
- Finish reason SAFETY/PROHIBITED_CONTENT/BLOCKLIST/SPII (or a blocked prompt) → ``blocked_safety``.

Error messages are truncated and scrubbed of the key before they leave this module (SEC-13).
"""

from __future__ import annotations

import functools
import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from support_agent.config import GEMINI_MIN_TIMEOUT_S, ConfigError, Settings
from support_agent.llm.base import (
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
    parse_json_object,
    provider_error,
)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/"

BLOCKED_FINISH_REASONS = frozenset(
    {
        "SAFETY",
        "PROHIBITED_CONTENT",
        "BLOCKLIST",
        "SPII",
        "IMAGE_SAFETY",
        "IMAGE_PROHIBITED_CONTENT",
    }
)
_AUTH_STATUSES = frozenset({"UNAUTHENTICATED", "PERMISSION_DENIED", "FAILED_PRECONDITION"})
_AUTH_HINT_RE = re.compile(r"api[\s_-]?key|billing", re.I)
_DAILY_HINT_RE = re.compile(r"per[\s_-]?day|daily|\"quotaValue\":\s*\"0\"|limit:\s*0\b", re.I)
_MAX_MESSAGE_CHARS = 300

_TOOL_MODES = {
    "auto": types.FunctionCallingConfigMode.AUTO,
    "none": types.FunctionCallingConfigMode.NONE,
}


class GeminiClient:
    """``LLMClient`` over the Gemini API. One instance per batch (it holds breaker state)."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if settings.api_key is None:
            raise ConfigError(f"{settings.credential_env_var} is required for the Gemini provider")
        self._settings = settings
        self._secret = settings.api_key.reveal()
        self._client = client if client is not None else self._make_sdk_client(settings)
        self.runner = AttemptRunner(
            settings.primary_model,
            settings.fallback_model,
            max_attempts=settings.max_attempts,
            timeout_s=max(settings.timeout_s, GEMINI_MIN_TIMEOUT_S),
            sleep=sleep,
            clock=clock,
        )

    @staticmethod
    def _make_sdk_client(settings: Settings) -> genai.Client:
        assert settings.api_key is not None
        return genai.Client(
            api_key=settings.api_key.reveal(),
            vertexai=False,
            http_options=types.HttpOptions(
                base_url=GEMINI_BASE_URL,
                timeout=_timeout_ms(settings.timeout_s),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def generate(self, req: LLMRequest) -> LLMResponse:
        contents = to_contents(req.contents)

        def attempt(model: str, timeout_s: float) -> AttemptOutput:
            if req.deadline is not None and timeout_s < GEMINI_MIN_TIMEOUT_S:
                raise ProviderError(
                    "timeout",
                    f"case deadline leaves {timeout_s:.1f} s, below the "
                    f"{GEMINI_MIN_TIMEOUT_S:g} s minimum request deadline",
                    model=model,
                )
            config = self.build_config(req, timeout_s)
            try:
                response = self._client.models.generate_content(
                    model=model, contents=contents, config=config
                )
            except Exception as exc:
                err = classify_exception(exc, model=model, secret=self._secret)
                if err is None:
                    raise
                raise err from None
            return to_attempt_output(response, model=model)

        return self.runner.run(attempt, deadline=req.deadline)

    def build_config(self, req: LLMRequest, timeout_s: float) -> types.GenerateContentConfig:
        config: dict[str, Any] = {
            "system_instruction": req.system,
            "max_output_tokens": req.max_output_tokens or self._settings.max_output_tokens,
            "candidate_count": 1,
            "thinking_config": types.ThinkingConfig(
                thinking_level=types.ThinkingLevel(self._settings.thinking_level.upper())
            ),
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
            "http_options": types.HttpOptions(
                timeout=_timeout_ms(timeout_s),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        }
        if req.tools:
            config["tools"] = [to_tool(req.tools)]
            config["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=_TOOL_MODES[req.tool_mode])
            )
        if req.response_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = response_schema_for(req.response_schema)
        return types.GenerateContentConfig(**config)


# --- request conversion -----------------------------------------------------------------------


def to_contents(messages: Sequence[Message]) -> list[types.Content]:
    """Normalized history → SDK contents. Model turns pass through untouched; consecutive tool
    results share one user turn (one function response per call of the preceding turn)."""
    contents: list[types.Content] = []
    for msg in messages:
        if isinstance(msg, UserMessage):
            contents.append(types.Content(role="user", parts=[types.Part(text=msg.text)]))
        elif isinstance(msg, ModelTurn):
            if not isinstance(msg.raw, types.Content):
                raise TypeError("ModelTurn.raw must be the types.Content returned by Gemini")
            contents.append(msg.raw)
        elif isinstance(msg, ToolResult):
            part = types.Part(
                function_response=types.FunctionResponse(
                    name=msg.name, response=dict(msg.response), id=msg.call_id
                )
            )
            prev = contents[-1] if contents else None
            if prev is not None and prev.role == "user" and _all_function_responses(prev):
                prev.parts = [*(prev.parts or []), part]
            else:
                contents.append(types.Content(role="user", parts=[part]))
        else:
            raise TypeError(f"unsupported message type {type(msg).__name__}")
    return contents


def _all_function_responses(content: types.Content) -> bool:
    return bool(content.parts) and all(p.function_response for p in content.parts or [])


def to_tool(declarations: Sequence[Mapping[str, Any]]) -> types.Tool:
    """JSON-schema tool declarations (``tools.py`` format) → one SDK ``Tool``."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=d["name"],
                description=d.get("description"),
                parameters=_schema(d["parameters"]) if d.get("parameters") else None,
            )
            for d in declarations
        ]
    )


def response_schema_for(model: type[BaseModel]) -> types.Schema:
    """Pydantic model → the OpenAPI-subset ``responseSchema`` verified by smoke test S-001,
    with properties kept in declaration order (a fresh copy per call)."""
    return _cached_response_schema(model).model_copy(deep=True)


@functools.cache
def _cached_response_schema(model: type[BaseModel]) -> types.Schema:
    schema = _schema(model.model_json_schema())
    schema.property_ordering = list(schema.properties or {})
    return schema


def _schema(json_schema: Mapping[str, Any]) -> types.Schema:
    return types.Schema.from_json_schema(
        json_schema=types.JSONSchema.model_validate(dict(json_schema)),
        api_option="GEMINI_API",
    )


def _timeout_ms(timeout_s: float) -> int:
    """SDK timeout in ms, never below the API's minimum request deadline."""
    return int(max(timeout_s, GEMINI_MIN_TIMEOUT_S) * 1000)


# --- response normalization -----------------------------------------------------------------


def to_attempt_output(response: types.GenerateContentResponse, *, model: str) -> AttemptOutput:
    """One SDK response → normalized output; raises ``blocked_safety`` for blocked content."""
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason:
        raise ProviderError(
            "blocked_safety", f"prompt blocked: {_enum_name(feedback.block_reason)}", model=model
        )
    usage = to_usage(response.usage_metadata)
    candidates = response.candidates or []
    if not candidates:
        return AttemptOutput(usage=usage)

    candidate = candidates[0]
    finish = _enum_name(candidate.finish_reason) if candidate.finish_reason else None
    if finish in BLOCKED_FINISH_REASONS:
        raise ProviderError("blocked_safety", f"finish_reason={finish}", model=model)

    content = candidate.content
    parts = (content.parts if content else None) or []
    calls = tuple(
        FunctionCall(
            name=p.function_call.name or "",
            args=dict(p.function_call.args or {}),
            call_id=p.function_call.id,
        )
        for p in parts
        if p.function_call is not None
    )
    text = "".join(p.text for p in parts if p.text and not p.thought)
    return AttemptOutput(
        function_calls=calls,
        final_json=None if calls else parse_json_object(text),
        text=text,
        raw_model_turn=content,
        usage=usage,
        finish_reason=finish,
    )


def to_usage(metadata: types.GenerateContentResponseUsageMetadata | None) -> Usage:
    """Token usage; every missing count (``None``) becomes 0."""
    if metadata is None:
        return Usage()
    return Usage(
        input=metadata.prompt_token_count or 0,
        output=metadata.candidates_token_count or 0,
        cached=metadata.cached_content_token_count or 0,
        thoughts=metadata.thoughts_token_count or 0,
    )


def _enum_name(value: Any) -> str:
    return str(getattr(value, "value", value))


# --- error classification -------------------------------------------------------------------


def classify_exception(
    exc: BaseException, *, model: str | None = None, secret: str | None = None
) -> ProviderError | None:
    """Map an SDK/transport exception to a ``ProviderError``; ``None`` if it is not one."""
    if isinstance(exc, errors.APIError):
        kind = classify_api_error(exc)
        message = f"HTTP {exc.code} {exc.status or ''}: {exc.message or ''}"
    elif isinstance(exc, httpx.TimeoutException | TimeoutError):
        kind, message = "timeout", f"client timeout ({type(exc).__name__})"
    elif isinstance(exc, httpx.TransportError):
        kind, message = "server_5xx", f"transport failure ({type(exc).__name__})"
    else:
        return None
    return provider_error(kind, _sanitize(message, secret), model=model)


def classify_api_error(exc: errors.APIError) -> str:
    code = exc.code or 0
    status = (exc.status or "").upper()
    blob = f"{exc.message or ''} {_details_text(exc.details)}"
    if code in (401, 403) or status in _AUTH_STATUSES:
        return "auth_billing"
    if code == 400 and _AUTH_HINT_RE.search(blob):
        return "auth_billing"
    if code == 404:
        return "model_not_found"
    if code == 408:
        return "timeout"
    if code == 429:
        return "quota_daily" if _DAILY_HINT_RE.search(blob) else "rate_limit_minute"
    if 400 <= code < 500:
        return "bad_request"
    return "server_5xx"


def _details_text(details: Any) -> str:
    try:
        return json.dumps(details, default=str)
    except (TypeError, ValueError):
        return str(details)


def _sanitize(message: str, secret: str | None) -> str:
    if secret:
        message = message.replace(secret, "[REDACTED]")
    message = " ".join(message.split())
    return message[:_MAX_MESSAGE_CHARS]
