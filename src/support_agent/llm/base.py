"""Provider-agnostic LLM contract (architecture §3.3, §3.4, §7).

- ``FinalAnswer``: the canonical structured answer (§3.3). Providers constrain generation with its
  schema; the agent re-validates the parsed JSON against it.
- ``LLMRequest`` / ``LLMResponse``: normalized request/response types. History may hold opaque
  provider-native model turns (``ModelTurn``) that are replayed **unchanged**, so Gemini 3 thought
  signatures survive the tool round.
- ``ProviderError(kind=...)``: the error taxonomy of §7; ``AuthBillingError`` is the dedicated
  subclass the agent/CLI turns into the batch circuit breaker.
- ``AttemptRunner``: the one implementation of the §7 retry/fallback table, shared by every
  client (Gemini and the fake), so offline tests exercise exactly the production semantics.

Terminology (§7): one ``generate()`` call is one **semantic call**; it makes at most
``max_attempts`` **transport attempts** in total, across the primary and fallback models.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict, Field

# --- Final answer schema (architecture §3.3) ------------------------------------------------

ANSWER_MAX_CHARS = 1200

EscalationReason = Literal[
    "none",
    "dispute",
    "hardship",
    "fraud",
    "decline_or_limit",
    "fee_dispute",
    "credit_report",
    "refund_overdue",
    "human_requested",
    "out_of_policy_action",
    "other",
]
ESCALATION_REASONS: tuple[str, ...] = get_args(EscalationReason)


class FinalAnswer(BaseModel):
    """The model's structured reply. ``escalation_reason`` is ``"none"`` when not escalating."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    answer: str = Field(max_length=ANSWER_MAX_CHARS)
    escalation_reason: EscalationReason
    policy_applied: bool
    cited_policies: list[str]


def final_answer_json_schema() -> dict[str, Any]:
    """JSON schema of ``FinalAnswer`` (fresh copy); an input of ``PROMPT_VERSION``."""
    return FinalAnswer.model_json_schema()


# --- Error taxonomy and the retry/fallback table (architecture §7) --------------------------

ErrorClass = Literal[
    "rate_limit_minute",
    "quota_daily",
    "overloaded",
    "server_5xx",
    "timeout",
    "model_not_found",
    "bad_request",
    "auth_billing",
    "blocked_safety",
]
"""Transport-level error classes raised by clients. The agent-level classes of §7
(``malformed_output``, ``validation_exhausted``, ``batch_limit``) are not provider errors:
malformed output is a *successful* attempt whose ``LLMResponse.malformed`` is true."""

ERROR_CLASSES: tuple[str, ...] = get_args(ErrorClass)


@dataclass(frozen=True)
class RetryRule:
    same_model_retry: bool
    fallback_eligible: bool
    backoff: bool = False
    disable_model_for_batch: bool = False


RETRY_TABLE: Mapping[str, RetryRule] = {
    "rate_limit_minute": RetryRule(same_model_retry=True, fallback_eligible=True, backoff=True),
    "quota_daily": RetryRule(
        same_model_retry=False, fallback_eligible=True, disable_model_for_batch=True
    ),
    # Server-side overload (503 UNAVAILABLE / 504 DEADLINE_EXCEEDED): retrying the same model
    # rarely helps and burns the case deadline, so go straight to the fallback model.
    "overloaded": RetryRule(same_model_retry=False, fallback_eligible=True),
    "server_5xx": RetryRule(same_model_retry=True, fallback_eligible=True, backoff=True),
    "timeout": RetryRule(same_model_retry=True, fallback_eligible=True),
    "model_not_found": RetryRule(same_model_retry=False, fallback_eligible=True),
    "bad_request": RetryRule(same_model_retry=False, fallback_eligible=False),
    "auth_billing": RetryRule(same_model_retry=False, fallback_eligible=False),
    "blocked_safety": RetryRule(same_model_retry=False, fallback_eligible=False),
}

MAX_BACKOFF_S = 1.0
MIN_BACKOFF_S = 0.25
MIN_ATTEMPT_BUDGET_S = 0.5
"""A further attempt starts only if at least this much of the case deadline remains (default of
``AttemptRunner(min_attempt_s=...)``; the Gemini adapter raises it to the API minimum)."""

# Batch-scoped primary-model health breaker (architecture §7).
BREAKER_ERROR_CLASSES = frozenset({"overloaded", "timeout"})
PRIMARY_BREAKER_THRESHOLD = 2
"""Consecutive ``BREAKER_ERROR_CLASSES`` failures on the primary that start a cooldown."""
PRIMARY_COOLDOWN_CALLS = 20
"""Semantic calls (≈ 10 cases at ~2 calls each) that start on the fallback during a cooldown."""

AttemptStatus = Literal["ok", "retry", "fallback", "failed"]
AttemptReason = Literal[
    "primary", "primary_probe", "primary_cooldown", "primary_disabled", "failover", "retry"
]
"""Why an attempt went to its model: ``primary`` (normal start), ``primary_probe`` (first primary
call after a cooldown), ``primary_cooldown`` (started on the fallback: primary cooling down),
``primary_disabled`` (started on the fallback: primary hit ``quota_daily``), ``failover`` (next
model after a fallback-eligible error), ``retry`` (same model again)."""


@dataclass(frozen=True)
class AttemptRecord:
    """One transport attempt, for the trace. ``status`` is what happened *next*: ``ok`` (success),
    ``retry`` (same model again), ``fallback`` (next model), ``failed`` (terminal); ``reason`` is
    why this attempt went to ``model`` (``AttemptReason``)."""

    model: str
    status: AttemptStatus
    error_class: str | None
    latency_ms: int
    reason: AttemptReason = "primary"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "reason": self.reason,
            "status": self.status,
            "error_class": self.error_class,
            "latency_ms": self.latency_ms,
        }


class ProviderError(Exception):
    """A classified provider/transport failure. Messages never contain credentials.
    ``fallback_used``: some attempt of the failed semantic call went to the fallback model."""

    def __init__(
        self,
        kind: str,
        message: str = "",
        *,
        model: str | None = None,
        attempts: Sequence[AttemptRecord] = (),
        fallback_used: bool = False,
    ) -> None:
        if kind not in ERROR_CLASSES:
            raise ValueError(f"unknown provider error kind {kind!r}")
        super().__init__(f"{kind}: {message}" if message else kind)
        self.kind = kind
        self.message = message
        self.model = model
        self.attempts: tuple[AttemptRecord, ...] = tuple(attempts)
        self.fallback_used = fallback_used

    @property
    def rule(self) -> RetryRule:
        return RETRY_TABLE[self.kind]

    def with_attempts(
        self, attempts: Sequence[AttemptRecord], *, fallback_used: bool = False
    ) -> ProviderError:
        """Same error class (and subclass), carrying the attempt records of the semantic call."""
        return type(self)(
            self.kind,
            self.message,
            model=self.model,
            attempts=attempts,
            fallback_used=fallback_used,
        )


class AuthBillingError(ProviderError):
    """Invalid key, permission or billing failure: never retried; opens the batch breaker."""

    def __init__(
        self,
        kind: str = "auth_billing",
        message: str = "",
        *,
        model: str | None = None,
        attempts: Sequence[AttemptRecord] = (),
        fallback_used: bool = False,
    ) -> None:
        super().__init__(
            "auth_billing", message, model=model, attempts=attempts, fallback_used=fallback_used
        )


def provider_error(kind: str, message: str = "", *, model: str | None = None) -> ProviderError:
    """Build the right exception type for ``kind``."""
    cls = AuthBillingError if kind == "auth_billing" else ProviderError
    return cls(kind, message, model=model)


# --- Normalized request/response (architecture §3.4) ----------------------------------------

ToolMode = Literal["auto", "none"]


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class ModelTurn:
    """A provider-native model turn (``LLMResponse.raw_model_turn``), replayed unchanged."""

    raw: Any


@dataclass(frozen=True)
class ToolResult:
    name: str
    response: Mapping[str, Any]
    call_id: str | None = None


Message = UserMessage | ModelTurn | ToolResult


@dataclass(frozen=True)
class LLMRequest:
    """One semantic call. ``tools`` are plain JSON-schema declarations (``tools.py`` format);
    ``max_output_tokens=None`` uses the client's configured default; ``deadline`` is an
    absolute ``time.monotonic()`` value bounding every attempt of this call."""

    system: str
    contents: tuple[Message, ...]
    tools: tuple[Mapping[str, Any], ...] = ()
    tool_mode: ToolMode = "auto"
    response_schema: type[BaseModel] | None = FinalAnswer
    max_output_tokens: int | None = None
    deadline: float | None = None


@dataclass(frozen=True)
class FunctionCall:
    name: str
    args: dict[str, Any]
    call_id: str | None = None


@dataclass(frozen=True)
class Usage:
    input: int = 0
    output: int = 0
    cached: int = 0
    thoughts: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "input": self.input,
            "output": self.output,
            "cached": self.cached,
            "thoughts": self.thoughts,
        }


@dataclass(frozen=True)
class AttemptOutput:
    """What one successful transport attempt yields (before attempt bookkeeping)."""

    function_calls: tuple[FunctionCall, ...] = ()
    final_json: dict[str, Any] | None = None
    text: str = ""
    raw_model_turn: Any = None
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Normalized result of one semantic call.

    ``final_json`` is the parsed JSON object (not yet validated as ``FinalAnswer``) when the
    model answered; ``function_calls`` when it called tools. Neither → ``malformed`` (the agent
    routes it to the repair call, §7 ``malformed_output``)."""

    function_calls: tuple[FunctionCall, ...]
    final_json: dict[str, Any] | None
    text: str
    raw_model_turn: Any
    usage: Usage
    model_id: str
    latency_ms: int
    attempts: tuple[AttemptRecord, ...]
    finish_reason: str | None = None
    fallback_used: bool = False
    """Some attempt of this semantic call went to the fallback model."""

    @property
    def malformed(self) -> bool:
        return not self.function_calls and self.final_json is None


class LLMClient(Protocol):
    def generate(self, req: LLMRequest) -> LLMResponse:
        """One semantic call. Raises ``ProviderError`` (``AuthBillingError`` for auth/billing)."""
        ...


def parse_json_object(text: str) -> dict[str, Any] | None:
    """The text as a JSON object, or ``None`` if it is not exactly one JSON object."""
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


# --- Retry / fallback engine (architecture §7) ----------------------------------------------

Attempt = Callable[[str, float], AttemptOutput]
"""``attempt(model, timeout_s)`` performs one transport attempt or raises ``ProviderError``."""


class AttemptRunner:
    """Executes one semantic call under the §7 table; holds per-batch model state.

    - At most ``max_attempts`` transport attempts per call, primary + fallback combined.
    - Order: first model → the other model on a fallback-eligible error → at most one same-model
      retry (only for retry-eligible classes, on the model that just failed; short jittered
      backoff ≤ 1 s for ``rate_limit_minute``/``server_5xx``). So a transient error never
      prevents one fallback attempt when a fallback is configured and time allows.
    - ``overloaded`` is never retried on the same model: it goes to the fallback.
    - Every attempt uses the same credential; only the model ID changes (OD-16).
    - ``quota_daily`` disables that model for the rest of the batch.
    - ``auth_billing`` is never retried and latches: every later call raises ``AuthBillingError``
      without any transport attempt.
    - Primary health breaker: after ``breaker_threshold`` consecutive ``overloaded``/``timeout``
      failures on the primary, the next ``cooldown_calls`` semantic calls start on the fallback
      (primary stays second); then one call probes the primary, and a single further failure
      re-opens the cooldown. Operational state only (no user data), per batch like the rest.
    - With a ``deadline``, an attempt starts only if ≥ ``min_attempt_s`` remain, and its timeout
      is capped by the remaining time.
    """

    def __init__(
        self,
        primary_model: str,
        fallback_model: str | None,
        *,
        max_attempts: int,
        timeout_s: float,
        min_attempt_s: float = MIN_ATTEMPT_BUDGET_S,
        breaker_threshold: int = PRIMARY_BREAKER_THRESHOLD,
        cooldown_calls: int = PRIMARY_COOLDOWN_CALLS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if breaker_threshold < 1 or cooldown_calls < 0:
            raise ValueError("breaker_threshold must be >= 1 and cooldown_calls >= 0")
        models = [primary_model]
        if fallback_model and fallback_model != primary_model:
            models.append(fallback_model)
        self.models: tuple[str, ...] = tuple(models)
        self.primary_model = primary_model
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s
        self.min_attempt_s = min_attempt_s
        self.breaker_threshold = breaker_threshold
        self.cooldown_calls = cooldown_calls
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        self.disabled_models: set[str] = set()
        self.auth_failed = False
        self.primary_strikes = 0
        self.cooldown_left = 0
        self.cooldowns_started = 0
        self._probe_next = False

    def run(self, attempt: Attempt, *, deadline: float | None = None) -> LLMResponse:
        if self.auth_failed:
            raise AuthBillingError(message="circuit breaker open after an auth/billing failure")

        started = self._clock()
        if not self._available():
            raise ProviderError("quota_daily", "every configured model is exhausted for this batch")
        if not self._time_left(deadline, started):
            raise ProviderError("timeout", "case deadline exhausted before the first attempt")

        records: list[AttemptRecord] = []
        candidates, reason = self._plan()
        model_idx = 0
        model = candidates[0]
        retried: set[str] = set()
        while True:
            timeout_s = self.timeout_s
            if deadline is not None:
                timeout_s = min(timeout_s, deadline - self._clock())
            t0 = self._clock()
            try:
                out = attempt(model, timeout_s)
            except ProviderError as err:
                latency = _ms(self._clock() - t0)
                rule = err.rule
                if err.kind == "auth_billing":
                    self.auth_failed = True
                if rule.disable_model_for_batch:
                    self.disabled_models.add(model)
                self._observe(model, err.kind)

                budget_left = len(records) + 1 < self.max_attempts and self._time_left(
                    deadline, self._clock()
                )
                if budget_left and rule.fallback_eligible and model_idx + 1 < len(candidates):
                    records.append(AttemptRecord(model, "fallback", err.kind, latency, reason))
                    model_idx += 1
                    model, reason = candidates[model_idx], "failover"
                    continue
                if budget_left and rule.same_model_retry and model not in retried:
                    records.append(AttemptRecord(model, "retry", err.kind, latency, reason))
                    retried.add(model)
                    reason = "retry"
                    if rule.backoff:
                        self._backoff(deadline)
                        if not self._time_left(deadline, self._clock()):
                            records[-1] = replace(records[-1], status="failed")
                            raise self._failure(err, records) from err
                    continue
                records.append(AttemptRecord(model, "failed", err.kind, latency, reason))
                raise self._failure(err, records) from err

            self._observe(model, None)
            records.append(AttemptRecord(model, "ok", None, _ms(self._clock() - t0), reason))
            return LLMResponse(
                function_calls=out.function_calls,
                final_json=out.final_json,
                text=out.text,
                raw_model_turn=out.raw_model_turn,
                usage=out.usage,
                model_id=model,
                latency_ms=_ms(self._clock() - started),
                attempts=tuple(records),
                finish_reason=out.finish_reason,
                fallback_used=self._fallback_used(records),
            )

    def _available(self) -> list[str]:
        return [m for m in self.models if m not in self.disabled_models]

    def _plan(self) -> tuple[list[str], AttemptReason]:
        """Model order for this call and why its first model was chosen (advances the cooldown)."""
        candidates = self._available()
        if candidates[0] != self.primary_model:
            return candidates, "primary_disabled"
        if len(candidates) > 1 and self.cooldown_left > 0:
            self.cooldown_left -= 1
            if self.cooldown_left == 0:
                # Half-open: the next call probes the primary; one more failure re-opens.
                self._probe_next = True
                self.primary_strikes = self.breaker_threshold - 1
            return [candidates[1], candidates[0]], "primary_cooldown"
        if self._probe_next:
            self._probe_next = False
            return candidates, "primary_probe"
        return candidates, "primary"

    def _observe(self, model: str, error_class: str | None) -> None:
        """Track consecutive overload/timeout failures of the primary (only with a fallback)."""
        if model != self.primary_model or len(self.models) < 2:
            return
        if error_class not in BREAKER_ERROR_CLASSES:
            self.primary_strikes = 0
            return
        self.primary_strikes += 1
        if self.primary_strikes >= self.breaker_threshold and self.cooldown_calls > 0:
            self.primary_strikes = 0
            self.cooldown_left = self.cooldown_calls
            self.cooldowns_started += 1
            self._probe_next = False

    def _fallback_used(self, records: Sequence[AttemptRecord]) -> bool:
        return any(r.model != self.primary_model for r in records)

    def _failure(self, err: ProviderError, records: list[AttemptRecord]) -> ProviderError:
        return err.with_attempts(records, fallback_used=self._fallback_used(records))

    def _time_left(self, deadline: float | None, now: float) -> bool:
        return deadline is None or deadline - now >= self.min_attempt_s

    def _backoff(self, deadline: float | None) -> None:
        delay = MIN_BACKOFF_S + (MAX_BACKOFF_S - MIN_BACKOFF_S) * self._rng()
        if deadline is not None:
            delay = min(delay, max(0.0, deadline - self._clock() - self.min_attempt_s))
        if delay > 0:
            self._sleep(delay)


def _ms(seconds: float) -> int:
    return max(0, round(seconds * 1000))
