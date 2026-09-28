"""The per-case loop, ``answer_case`` (architecture §5).

Steps: input guard → tripwire (fraud mode withholds the tool) → request build → call #1 (tools
``auto``) → execute **only** the first registered tool call, record the others → call #2 (tool
mode ``none``) → validate → at most one repair call (tool mode ``none``) → else the SEC-10 safe
failure. The route is derived by code (§6) and a ``TraceRecord`` is returned with the result.

The model writes every substantive answer (ADR-1, SEZ-F01): the only text code ever returns is
``SAFE_FAILURE_ANSWER``. ``answer_case`` is a pure function of (resources, llm, case) plus the
per-batch objects the caller passes in (``AgentStatics``, ``CallBudget``); all per-case state
lives in a fresh ``_CaseRun`` and nothing is kept at module level (OWN-04, SEC-12).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from support_agent.guards import (
    SAFE_FAILURE_ANSWER,
    CheckVerdict,
    GuardedInput,
    InputGuard,
    OutputValidator,
    Tripwire,
    TripwireResult,
    ValidationContext,
    ValidationResult,
)
from support_agent.llm.base import (
    FinalAnswer,
    LLMClient,
    LLMRequest,
    LLMResponse,
    Message,
    ModelTurn,
    ProviderError,
    ToolMode,
    ToolResult,
    UserMessage,
)
from support_agent.prompts import PromptBundle, build_case_message
from support_agent.resources import Resources
from support_agent.routing import Route, derive_route, ensure_route
from support_agent.tools import Toolset, build_toolset
from support_agent.trace import LLMCallRecord, ToolCallRecord, TraceRecord, trace_args

MAX_SEMANTIC_CALLS_PER_CASE = 3

# Function responses for calls that are not executed. They carry no data, only an instruction.
_REJECTED_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "extra_call": "Not executed: only one tool call per conversation is allowed.",
        "unknown_tool": "Not executed: no tool with this name is available.",
        "invalid_args": "Not executed: invalid arguments",
    }
)


@dataclass(frozen=True)
class Case:
    """One input line. Extra keys of the input (e.g. golden-set labels) are ignored (SEZ-C02)."""

    id: str
    user_id: str
    question: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Case:
        case_id, user_id, question = data.get("id"), data.get("user_id"), data.get("question")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("'id' must be a non-empty string")
        if not isinstance(user_id, str):
            raise ValueError("'user_id' must be a string")
        if not isinstance(question, str):
            raise ValueError("'question' must be a string")
        return cls(id=case_id, user_id=user_id, question=question)


@dataclass(frozen=True)
class CaseResult:
    id: str
    route: Route
    answer: str
    trace: TraceRecord

    @property
    def error_class(self) -> str | None:
        return self.trace.error_class

    @property
    def safe_failure(self) -> bool:
        return self.trace.safe_failure

    def answer_line(self) -> dict[str, str]:
        """Exactly the contract keys ``{id, route, answer}`` (SEZ-C03)."""
        return {"id": self.id, "route": ensure_route(self.route), "answer": self.answer}


class BatchLimitReached(Exception):
    """``MAX_LLM_CALLS_PER_BATCH`` is used up (architecture §7 ``batch_limit``)."""


class CallBudget:
    """Batch-level semantic-call counter (SEC-07). The CLI creates one per batch and passes it to
    every ``answer_case``; it is never module state."""

    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self.limit = limit
        self.used = 0

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit

    def take(self) -> None:
        if self.exhausted:
            raise BatchLimitReached(f"MAX_LLM_CALLS_PER_BATCH={self.limit} reached")
        self.used += 1


@dataclass(frozen=True)
class AgentStatics:
    """Immutable per-batch objects derived from ``Resources`` (built once, shared by cases)."""

    prompts: PromptBundle
    validator: OutputValidator
    tripwire: Tripwire

    @classmethod
    def build(cls, resources: Resources) -> AgentStatics:
        return cls(
            prompts=PromptBundle.build(resources.policies),
            validator=OutputValidator(resources.policies),
            tripwire=Tripwire(),
        )


def answer_case(
    resources: Resources,
    llm: LLMClient,
    case: Case,
    *,
    statics: AgentStatics | None = None,
    budget: CallBudget | None = None,
    run_id: str | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> CaseResult:
    """Answer one case. Provider errors and batch-limit exhaustion become the SEC-10 line with the
    error class in the trace; an ``AuthBillingError`` yields ``error_class == "auth_billing"``,
    which the caller turns into the batch circuit breaker."""
    run = _CaseRun(
        resources=resources,
        llm=llm,
        case=case,
        statics=statics or AgentStatics.build(resources),
        budget=budget,
        run_id=run_id,
        clock=clock,
    )
    return run.execute()


def safe_failure_result(
    case_id: str,
    user_id: str,
    error_class: str,
    statics: AgentStatics,
    *,
    run_id: str | None = None,
) -> CaseResult:
    """The SEC-10 line for a case that makes no LLM call (breaker open, invalid input, crash)."""
    trace = TraceRecord(
        id=case_id,
        user_id=user_id,
        run_id=run_id,
        prompt_version=statics.prompts.prompt_version,
        corpus_hash=statics.prompts.corpus_hash,
        model=None,
        llm_calls=(),
        fallback_used=False,
        tool_calls=(),
        input={},
        tripwire={},
        validator=(),
        repair_attempted=False,
        escalation_reason=None,
        policy_applied=None,
        cited_policies=(),
        route_inputs={
            "forced_reason": None,
            "escalation_reason": None,
            "tool_executed": False,
            "policy_applied": None,
        },
        route_final="escalate",
        tokens={"input": 0, "output": 0, "cached": 0, "thoughts": 0},
        latency_ms=0,
        error_class=error_class,
        safe_failure=True,
    )
    return CaseResult(id=case_id, route="escalate", answer=SAFE_FAILURE_ANSWER, trace=trace)


class _ValidationExhausted(Exception):
    pass


class _CaseRun:
    """All mutable state of one case; created fresh by ``answer_case`` and then discarded."""

    def __init__(
        self,
        *,
        resources: Resources,
        llm: LLMClient,
        case: Case,
        statics: AgentStatics,
        budget: CallBudget | None,
        run_id: str | None,
        clock: Callable[[], float],
    ) -> None:
        self.resources = resources
        self.llm = llm
        self.case = case
        self.statics = statics
        self.budget = budget
        self.run_id = run_id
        self.clock = clock
        self.started = clock()

        self.calls: list[LLMCallRecord] = []
        self.tool_calls: list[ToolCallRecord] = []
        self.verdicts: list[dict[str, str]] = []
        self.tokens = {"input": 0, "output": 0, "cached": 0, "thoughts": 0}
        self.model: str | None = None
        self.fallback_used = False
        self.repair_attempted = False
        self.tool_executed = False
        self.tool_result: dict[str, Any] | None = None
        self.guarded: GuardedInput | None = None
        self.trip: TripwireResult | None = None

    # --- driver ---------------------------------------------------------------------------

    def execute(self) -> CaseResult:
        settings = self.resources.settings
        repo = self.resources.orders
        today = self.resources.today

        # 1. Input guard (SEC-05). An unknown user gets no special path: the tool finds nothing.
        guard = InputGuard(settings.input_char_cap, repo)
        guarded = guard.check(self.case.question, self.case.user_id)
        self.guarded = guarded
        # 2. Tripwire (SEC-09): a one-way signal; fraud mode withholds the order tool.
        trip = self.statics.tripwire.check(guarded.text)
        self.trip = trip
        toolset = None if trip.fraud_mode else build_toolset(self.case.user_id, repo, today)
        # 3. Request build: static prefix (system) + case message.
        contents: list[Message] = [
            UserMessage(build_case_message(guarded.text, today, trip.forced_reason))
        ]
        ctx_args = {"fraud_mode": trip.fraud_mode, "forced_reason": trip.forced_reason}

        try:
            final = self._run_loop(contents, toolset, ctx_args)
        except ProviderError as err:
            return self._safe_failure(err.kind)
        except BatchLimitReached:
            return self._safe_failure("batch_limit")
        except _ValidationExhausted:
            return self._safe_failure("validation_exhausted")
        return self._success(final)

    def _run_loop(
        self, contents: list[Message], toolset: Toolset | None, ctx_args: dict[str, Any]
    ) -> FinalAnswer:
        tools = tuple(toolset.declarations()) if toolset is not None else ()

        # 4. Call #1: the model may call get_my_orders once, or answer directly.
        response = self._call("initial", contents, tools, "auto")
        if response.function_calls:
            # 5. Tool execution: only the first registered call; the others are recorded.
            executed = self._run_tools(response, toolset, contents)
            if not executed:
                # Nothing ran (unknown tool / invalid args): malformed_output → repair call.
                # The rejected function responses already tell the model what went wrong.
                self.verdicts.append(
                    CheckVerdict(
                        "schema", "fail", "malformed_output: no valid tool call to execute"
                    ).to_dict()
                    | {"stage": "initial"}
                )
                return self._repair(contents, tools, ctx_args, note=None)
            # 6. Call #2: tool mode NONE, so the model structurally cannot call again.
            response = self._call("post_tool", contents, tools, "none")

        # 7. Validation, then at most one repair.
        result = self._validate(response, ctx_args, stage="initial")
        if result.ok:
            assert result.answer is not None
            return result.answer
        self._append_model_turn(response, contents, reason="extra_call")
        return self._repair(contents, tools, ctx_args, note=_repair_note(result))

    def _repair(
        self,
        contents: list[Message],
        tools: tuple[Mapping[str, Any], ...],
        ctx_args: dict[str, Any],
        *,
        note: str | None,
    ) -> FinalAnswer:
        self.repair_attempted = True
        if note is not None:
            contents.append(UserMessage(note))
        response = self._call("repair", contents, tools, "none")
        result = self._validate(response, ctx_args, stage="repair")
        if not result.ok:
            raise _ValidationExhausted
        assert result.answer is not None
        return result.answer

    # --- LLM calls --------------------------------------------------------------------------

    def _call(
        self,
        purpose: str,
        contents: list[Message],
        tools: tuple[Mapping[str, Any], ...],
        tool_mode: ToolMode,
    ) -> LLMResponse:
        if len(self.calls) >= MAX_SEMANTIC_CALLS_PER_CASE:  # defensive; the loop never exceeds it
            raise _ValidationExhausted
        if self.budget is not None:
            self.budget.take()
        request = LLMRequest(
            system=self.statics.prompts.system,
            contents=tuple(contents),
            tools=tools,
            tool_mode=tool_mode,
            response_schema=FinalAnswer,
            max_output_tokens=self.resources.settings.max_output_tokens,
        )
        try:
            response = self.llm.generate(request)
        except ProviderError as err:
            attempts = tuple(a.to_dict() for a in err.attempts)
            self.calls.append(LLMCallRecord(purpose, attempts, "error"))
            self.fallback_used |= any(a["status"] == "fallback" for a in attempts)
            raise
        outcome = (
            "function_calls"
            if response.function_calls
            else ("malformed" if response.malformed else "final")
        )
        self.calls.append(
            LLMCallRecord(purpose, tuple(a.to_dict() for a in response.attempts), outcome)
        )
        self.model = response.model_id
        self.fallback_used |= response.fallback_used
        usage = response.usage
        self.tokens["input"] += usage.input
        self.tokens["output"] += usage.output
        self.tokens["cached"] += usage.cached
        self.tokens["thoughts"] += usage.thoughts
        return response

    # --- tools ------------------------------------------------------------------------------

    def _run_tools(
        self, response: LLMResponse, toolset: Toolset | None, contents: list[Message]
    ) -> bool:
        """Execute the first call to a registered tool (if its args are valid); every other call
        gets a data-free rejected response. Returns whether the tool actually ran."""
        registered = toolset.names if toolset is not None else frozenset()
        declared = _declared_params(toolset)
        replies: list[ToolResult] = []
        attempted = False
        for call in response.function_calls:
            args = call.args
            if call.name in registered and not attempted:
                attempted = True
                problem = _args_problem(args, declared.get(call.name, frozenset()))
                if problem is None:
                    assert toolset is not None
                    result = toolset.execute(call.name, args)
                    self.tool_executed = True
                    self.tool_result = result
                    self.tool_calls.append(
                        ToolCallRecord(
                            name=call.name,
                            args=trace_args(args),
                            result_status=str(result.get("status")),
                            n_orders=len(result.get("orders") or []),
                        )
                    )
                    replies.append(ToolResult(call.name, result, call.call_id))
                    continue
                reason, detail = "invalid_args", problem
            elif call.name in registered:
                reason, detail = "extra_call", None
            else:
                reason, detail = "unknown_tool", None
            self.tool_calls.append(
                ToolCallRecord(
                    name=call.name[:100],
                    args=trace_args(args),
                    result_status="rejected",
                    reason=reason,
                )
            )
            replies.append(ToolResult(call.name, _rejected_payload(reason, detail), call.call_id))
        if response.raw_model_turn is not None:
            contents.append(ModelTurn(response.raw_model_turn))
        contents.extend(replies)
        return self.tool_executed

    def _append_model_turn(
        self, response: LLMResponse, contents: list[Message], *, reason: str
    ) -> None:
        """Replay the model's turn before the repair note; unexpected calls get rejected replies
        so the history stays well-formed for providers that pair calls with responses."""
        if response.raw_model_turn is not None:
            contents.append(ModelTurn(response.raw_model_turn))
        for call in response.function_calls:
            self.tool_calls.append(
                ToolCallRecord(
                    name=call.name[:100],
                    args=trace_args(call.args),
                    result_status="rejected",
                    reason=reason,
                )
            )
            contents.append(ToolResult(call.name, _rejected_payload(reason, None), call.call_id))

    # --- validation -------------------------------------------------------------------------

    def _validate(
        self, response: LLMResponse, ctx_args: dict[str, Any], *, stage: str
    ) -> ValidationResult:
        if response.function_calls:
            result = ValidationResult(
                verdicts=(
                    CheckVerdict(
                        "schema", "fail", "malformed_output: a tool call where an answer was due"
                    ),
                )
            )
        else:
            ctx = ValidationContext.for_case(
                self.resources.orders,
                self.case.user_id,
                self.guarded.text if self.guarded else "",
                tool_result=self.tool_result,
                **ctx_args,
            )
            result = self.statics.validator.validate(response.final_json, ctx)
        self.verdicts.extend({**v.to_dict(), "stage": stage} for v in result.verdicts)
        return result

    # --- results ----------------------------------------------------------------------------

    def _success(self, final: FinalAnswer) -> CaseResult:
        forced = self.trip.forced_reason if self.trip else None
        route = derive_route(
            forced_reason=forced,
            escalation_reason=final.escalation_reason,
            tool_executed=self.tool_executed,
            policy_applied=final.policy_applied,
        )
        trace = self._trace(
            route=route,
            escalation_reason=final.escalation_reason,
            policy_applied=final.policy_applied,
            cited=tuple(final.cited_policies),
            error_class=None,
        )
        return CaseResult(id=self.case.id, route=route, answer=final.answer, trace=trace)

    def _safe_failure(self, error_class: str) -> CaseResult:
        trace = self._trace(
            route="escalate",
            escalation_reason=None,
            policy_applied=None,
            cited=(),
            error_class=error_class,
        )
        return CaseResult(
            id=self.case.id, route="escalate", answer=SAFE_FAILURE_ANSWER, trace=trace
        )

    def _trace(
        self,
        *,
        route: Route,
        escalation_reason: str | None,
        policy_applied: bool | None,
        cited: tuple[str, ...],
        error_class: str | None,
    ) -> TraceRecord:
        forced = self.trip.forced_reason if self.trip else None
        return TraceRecord(
            id=self.case.id,
            user_id=self.case.user_id,
            run_id=self.run_id,
            prompt_version=self.statics.prompts.prompt_version,
            corpus_hash=self.statics.prompts.corpus_hash,
            model=self.model,
            llm_calls=tuple(self.calls),
            fallback_used=self.fallback_used,
            tool_calls=tuple(self.tool_calls),
            input=self.guarded.to_dict() if self.guarded else {},
            tripwire=self.trip.to_dict() if self.trip else {},
            validator=tuple(self.verdicts),
            repair_attempted=self.repair_attempted,
            escalation_reason=escalation_reason,
            policy_applied=policy_applied,
            cited_policies=cited,
            route_inputs={
                "forced_reason": forced,
                "escalation_reason": escalation_reason,
                "tool_executed": self.tool_executed,
                "policy_applied": policy_applied,
            },
            route_final=route,
            tokens=dict(self.tokens),
            latency_ms=max(0, round((self.clock() - self.started) * 1000)),
            error_class=error_class,
            safe_failure=error_class is not None,
        )


def _declared_params(toolset: Toolset | None) -> dict[str, frozenset[str]]:
    if toolset is None:
        return {}
    return {
        decl["name"]: frozenset((decl.get("parameters") or {}).get("properties") or {})
        for decl in toolset.declarations()
    }


def _args_problem(args: Any, allowed: frozenset[str]) -> str | None:
    """Structural check of model-supplied args. Pattern mismatches are left to the tool, which
    treats them as no match (architecture §3.2); a ``user_id`` is never honoured (SEC-01)."""
    if not isinstance(args, Mapping):
        return "arguments must be an object"
    unknown = sorted(str(k) for k in args if k not in allowed)
    if unknown:
        return f"unsupported argument(s) {unknown[:5]}"
    bad = sorted(str(k) for k, v in args.items() if v is not None and not isinstance(v, str))
    if bad:
        return f"argument(s) {bad} must be strings"
    return None


def _rejected_payload(reason: str, detail: str | None) -> dict[str, Any]:
    message = _REJECTED_MESSAGES[reason]
    if detail:
        message = f"{message}: {detail}."
    return {
        "status": "rejected",
        "error": message,
        "instruction": "Answer now with the final JSON answer; do not call tools.",
    }


def _repair_note(result: ValidationResult) -> str:
    """Short machine-generated list of the failed checks for the one repair call (step 7)."""
    return (
        "Your previous reply failed these automated checks:\n"
        f"{result.failure_summary()}\n"
        "Reply again with a corrected final answer as JSON in the required schema. "
        "Do not call tools."
    )
