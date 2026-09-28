"""Deterministic offline LLM for tests and CI (architecture §8, OWN-07).

Without a script, the **default fake responder** answers every call directly with
``DEFAULT_FAKE_ANSWER`` (route ``policy`` downstream), so the CLI runs fully offline.

With a script, each **transport attempt** consumes the next step, in order, across the whole
batch. Steps run through the same ``AttemptRunner`` as the Gemini adapter, so injected errors get
the real §7 retry/fallback treatment. Step forms (JSON objects)::

    {"final": {"answer": "...", "escalation_reason": "none", ...}}   # direct structured answer
    {"function_call": {"name": "get_my_orders", "args": {"order_id": "ord_1"}}}
    {"function_calls": [{"name": "...", "args": {...}}, ...]}         # several calls in one turn
    {"text": "not json"}                                               # raw text (malformed if not
                                                                       # a JSON object)
    {"error": "rate_limit_minute", "message": "optional"}              # injected ProviderError

Any step may add ``"usage": {"input": 1, "output": 2, "cached": 0, "thoughts": 0}`` and
``"finish_reason": "STOP"``. A ``FAKE_LLM_SCRIPT`` file holds either a list of steps or
``{"steps": [...], "on_exhausted": "error" | "default"}``; ``"default"`` switches to the default
responder once the steps run out, ``"error"`` (the default) raises ``FakeScriptExhausted``.
"""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from support_agent.config import ConfigError, Settings
from support_agent.llm.base import (
    ERROR_CLASSES,
    AttemptOutput,
    AttemptRunner,
    FunctionCall,
    LLMRequest,
    LLMResponse,
    Usage,
    parse_json_object,
    provider_error,
)

DEFAULT_FAKE_ANSWER: Mapping[str, Any] = {
    "answer": "[fake] offline answer",
    "escalation_reason": "none",
    "policy_applied": False,
    "cited_policies": [],
}

_STEP_KINDS = frozenset({"final", "function_call", "function_calls", "text", "error"})
_STEP_EXTRAS = frozenset({"usage", "finish_reason", "message"})
_ON_EXHAUSTED = frozenset({"error", "default"})


class FakeScriptExhausted(RuntimeError):
    """A scripted ``FakeLLM`` was asked for more attempts than its script holds."""


class FakeLLM:
    """Scripted ``LLMClient``. ``requests`` records every semantic call, ``attempt_models``
    every transport attempt's model, for assertions."""

    def __init__(
        self,
        script: Sequence[Mapping[str, Any]] | None = None,
        *,
        on_exhausted: str = "error",
        primary_model: str = "fake-primary",
        fallback_model: str | None = None,
        max_attempts: int = 2,
        timeout_s: float = 8.0,
        sleep: Callable[[float], None] = lambda _s: None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if on_exhausted not in _ON_EXHAUSTED:
            raise ValueError(f"on_exhausted must be one of {sorted(_ON_EXHAUSTED)}")
        self._steps: tuple[dict[str, Any], ...] | None = (
            None if script is None else tuple(_validate_step(i, s) for i, s in enumerate(script))
        )
        self._on_exhausted = on_exhausted
        self._cursor = 0
        self.runner = AttemptRunner(
            primary_model,
            fallback_model,
            max_attempts=max_attempts,
            timeout_s=timeout_s,
            sleep=sleep,
            clock=clock,
        )
        self.requests: list[LLMRequest] = []
        self.attempt_models: list[str] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> FakeLLM:
        """Fake mirroring the configured models/limits; replays ``FAKE_LLM_SCRIPT`` if set."""
        steps: list[dict[str, Any]] | None = None
        on_exhausted = "error"
        if settings.fake_llm_script is not None:
            steps, on_exhausted = load_script(settings.fake_llm_script)
        return cls(
            steps,
            on_exhausted=on_exhausted,
            primary_model=f"fake:{settings.primary_model}",
            fallback_model=f"fake:{settings.fallback_model}" if settings.fallback_model else None,
            max_attempts=settings.max_attempts,
            timeout_s=settings.timeout_s,
        )

    @property
    def remaining_steps(self) -> int | None:
        return None if self._steps is None else len(self._steps) - self._cursor

    def generate(self, req: LLMRequest) -> LLMResponse:
        self.requests.append(req)
        return self.runner.run(self._attempt, deadline=req.deadline)

    def _attempt(self, model: str, _timeout_s: float) -> AttemptOutput:
        self.attempt_models.append(model)
        step = self._next_step()
        if step is None:
            final = dict(copy.deepcopy(DEFAULT_FAKE_ANSWER))
            return AttemptOutput(
                final_json=final,
                text=json.dumps(final),
                raw_model_turn={"role": "model", "fake": "default"},
                finish_reason="STOP",
            )
        index, step = step
        if "error" in step:
            raise provider_error(step["error"], step.get("message", "injected by FakeLLM"))

        usage = Usage(**step.get("usage", {}))
        finish = step.get("finish_reason", "STOP")
        raw = {"role": "model", "fake_step": index, "content": copy.deepcopy(step)}
        if "final" in step:
            final = copy.deepcopy(step["final"])
            return AttemptOutput(
                final_json=final if isinstance(final, dict) else None,
                text=json.dumps(final),
                raw_model_turn=raw,
                usage=usage,
                finish_reason=finish,
            )
        if "text" in step:
            return AttemptOutput(
                final_json=parse_json_object(step["text"]),
                text=step["text"],
                raw_model_turn=raw,
                usage=usage,
                finish_reason=finish,
            )
        calls = step["function_calls"] if "function_calls" in step else [step["function_call"]]
        return AttemptOutput(
            function_calls=tuple(
                FunctionCall(
                    name=c["name"],
                    args=copy.deepcopy(c.get("args") or {}),
                    call_id=c.get("id") or f"fake_call_{index}_{n}",
                )
                for n, c in enumerate(calls)
            ),
            raw_model_turn=raw,
            usage=usage,
            finish_reason=finish,
        )

    def _next_step(self) -> tuple[int, dict[str, Any]] | None:
        if self._steps is None:
            return None
        if self._cursor >= len(self._steps):
            if self._on_exhausted == "default":
                return None
            raise FakeScriptExhausted(
                f"fake script exhausted after {len(self._steps)} step(s); add steps or set "
                f'"on_exhausted": "default"'
            )
        index = self._cursor
        self._cursor += 1
        return index, self._steps[index]


def load_script(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Parse a ``FAKE_LLM_SCRIPT`` file → (steps, on_exhausted). Raises ``ConfigError``."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"FAKE_LLM_SCRIPT {path}: cannot read JSON ({exc})") from None
    on_exhausted = "error"
    if isinstance(data, dict):
        on_exhausted = data.get("on_exhausted", "error")
        data = data.get("steps")
    if not isinstance(data, list) or on_exhausted not in _ON_EXHAUSTED:
        raise ConfigError(
            f'FAKE_LLM_SCRIPT {path}: expected a list of steps or {{"steps": [...], '
            f'"on_exhausted": "error"|"default"}}'
        )
    try:
        steps = [_validate_step(i, s) for i, s in enumerate(data)]
    except ValueError as exc:
        raise ConfigError(f"FAKE_LLM_SCRIPT {path}: {exc}") from None
    return steps, on_exhausted


def _validate_step(index: int, step: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(step, Mapping):
        raise ValueError(f"step {index}: must be an object")
    kinds = _STEP_KINDS & set(step)
    unknown = set(step) - _STEP_KINDS - _STEP_EXTRAS
    if len(kinds) != 1 or unknown:
        raise ValueError(
            f"step {index}: needs exactly one of {sorted(_STEP_KINDS)}"
            + (f"; unknown keys {sorted(unknown)}" if unknown else "")
        )
    (kind,) = kinds
    if kind == "error" and step["error"] not in ERROR_CLASSES:
        raise ValueError(f"step {index}: unknown error kind {step['error']!r}")
    if kind == "text" and not isinstance(step["text"], str):
        raise ValueError(f"step {index}: 'text' must be a string")
    if kind in {"function_call", "function_calls"}:
        calls = step[kind] if kind == "function_calls" else [step[kind]]
        if not isinstance(calls, list) or not calls:
            raise ValueError(f"step {index}: '{kind}' must be a non-empty call list/object")
        for call in calls:
            if not isinstance(call, Mapping) or not isinstance(call.get("name"), str):
                raise ValueError(f"step {index}: each function call needs a string 'name'")
            if not isinstance(call.get("args", {}), Mapping):
                raise ValueError(f"step {index}: function call 'args' must be an object")
    if "usage" in step:
        usage = step["usage"]
        if not isinstance(usage, Mapping) or set(usage) - {"input", "output", "cached", "thoughts"}:
            raise ValueError(f"step {index}: 'usage' keys are input/output/cached/thoughts")
    return copy.deepcopy(dict(step))
