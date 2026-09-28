"""Per-case trace record (architecture §10; schema in ``specs/evaluation.md`` §5).

One JSON line per case. It records metadata only: model IDs, transport attempts, tool-call
metadata (never tool results), tripwire and validator verdicts, route inputs, tokens and latency.
It never contains API keys, request headers, raw provider objects or environment data (SEC-13).
The bound ``user_id`` appears only in the top-level ``user_id`` field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

AGENT_ERROR_CLASSES: tuple[str, ...] = (
    "malformed_output",
    "validation_exhausted",
    "batch_limit",
    "invalid_input",
    "internal_error",
)
"""Terminal classes set by the agent/CLI, beyond the provider classes of ``llm.base``.
``invalid_input`` (OWN-14) and ``internal_error`` (unexpected exception, OWN-15) are additions
to the evaluation §5 list; both still produce the SEC-10 line."""

ARG_VALUE_MAX_CHARS = 100
ARGS_MAX_KEYS = 8


@dataclass(frozen=True)
class LLMCallRecord:
    """One semantic call (``initial`` | ``post_tool`` | ``repair``) and its transport attempts."""

    purpose: str
    attempts: tuple[dict[str, Any], ...]
    outcome: str
    """``final`` | ``function_calls`` | ``malformed`` | ``error``."""

    def to_dict(self) -> dict[str, Any]:
        return {"purpose": self.purpose, "attempts": list(self.attempts), "outcome": self.outcome}


@dataclass(frozen=True)
class ToolCallRecord:
    """Metadata of one model-proposed tool call; ``result_status`` ∈ ok | not_found | rejected."""

    name: str
    args: dict[str, Any]
    result_status: str
    n_orders: int = 0
    reason: str | None = None
    """Why a call was rejected: ``extra_call`` | ``unknown_tool`` | ``invalid_args``."""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "args": self.args,
            "result_status": self.result_status,
            "n_orders": self.n_orders,
        }
        if self.reason is not None:
            out["reason"] = self.reason
        return out


@dataclass(frozen=True)
class TraceRecord:
    id: str
    user_id: str
    run_id: str | None
    prompt_version: str
    corpus_hash: str
    model: str | None
    llm_calls: tuple[LLMCallRecord, ...]
    fallback_used: bool
    tool_calls: tuple[ToolCallRecord, ...]
    input: dict[str, Any]
    tripwire: dict[str, Any]
    validator: tuple[dict[str, str], ...]
    repair_attempted: bool
    escalation_reason: str | None
    policy_applied: bool | None
    cited_policies: tuple[str, ...]
    route_inputs: dict[str, Any]
    route_final: str
    tokens: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    error_class: str | None = None
    safe_failure: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "run_id": self.run_id,
            "prompt_version": self.prompt_version,
            "corpus_hash": self.corpus_hash,
            "model": self.model,
            "llm_calls": [c.to_dict() for c in self.llm_calls],
            "fallback_used": self.fallback_used,
            "tool_calls": [t.to_dict() for t in self.tool_calls],
            "input_truncated": bool(self.input.get("truncated", False)),
            "input": self.input,
            "tripwire": self.tripwire,
            "validator": list(self.validator),
            "repair_attempted": self.repair_attempted,
            "escalation_reason": self.escalation_reason,
            "policy_applied": self.policy_applied,
            "cited_policies": list(self.cited_policies),
            "route_inputs": self.route_inputs,
            "route_final": self.route_final,
            "tokens": self.tokens,
            "latency_ms": self.latency_ms,
            "error_class": self.error_class,
            "safe_failure": self.safe_failure,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=False)


def trace_args(args: Any) -> dict[str, Any]:
    """Model-proposed tool args, bounded so a hostile call cannot bloat the trace."""
    if not isinstance(args, dict):
        return {"_type": type(args).__name__}
    out: dict[str, Any] = {}
    for key in list(args)[:ARGS_MAX_KEYS]:
        value = args[key]
        if isinstance(value, str):
            value = value[:ARG_VALUE_MAX_CHARS]
        elif not isinstance(value, int | float | bool) and value is not None:
            value = f"<{type(value).__name__}>"
        out[str(key)[:ARG_VALUE_MAX_CHARS]] = value
    return out
