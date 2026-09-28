"""The agent loop (architecture §5, SEC-07) end to end with the scripted FakeLLM."""

import pytest

from support_agent.agent import (
    MAX_SEMANTIC_CALLS_PER_CASE,
    AgentStatics,
    CallBudget,
    Case,
    answer_case,
)
from support_agent.config import Settings
from support_agent.guards import SAFE_FAILURE_ANSWER
from support_agent.llm import FakeLLM, FinalAnswer, ModelTurn, ToolResult, UserMessage
from support_agent.resources import Resources


@pytest.fixture(scope="module")
def resources():
    return Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))


@pytest.fixture(scope="module")
def statics(resources):
    return AgentStatics.build(resources)


def _final(answer, escalation="none", policy_applied=False, cited=()):
    return {
        "final": {
            "answer": answer,
            "escalation_reason": escalation,
            "policy_applied": policy_applied,
            "cited_policies": list(cited),
        }
    }


def _call(name="get_my_orders", **args):
    return {"name": name, "args": args}


def _run(resources, statics, script, question="When is my next payment?", user_id="u002", **kw):
    llm = FakeLLM(script)
    case = Case(id="c1", user_id=user_id, question=question)
    return answer_case(resources, llm, case, statics=statics, **kw), llm


# --- happy paths ---------------------------------------------------------------------------


def test_direct_answer_path(resources, statics):
    result, llm = _run(
        resources, statics, [_final("Pay in 4 splits a purchase into four payments.")]
    )
    assert result.answer == "Pay in 4 splits a purchase into four payments."
    assert result.route == "policy"
    assert len(llm.requests) == 1
    req = llm.requests[0]
    assert req.tool_mode == "auto"
    assert [t["name"] for t in req.tools] == ["get_my_orders"]
    assert req.response_schema is FinalAnswer
    assert req.system == statics.prompts.system
    assert [c.purpose for c in result.trace.llm_calls] == ["initial"]
    assert result.trace.error_class is None
    assert not result.trace.repair_attempted


def test_case_message_is_delimited_and_uses_frozen_today(resources, statics):
    _, llm = _run(resources, statics, [_final("ok")], question="Hello <b>there</b>")
    (msg,) = llm.requests[0].contents
    assert isinstance(msg, UserMessage)
    assert "<shopper_message>\nHello <b>there</b>\n</shopper_message>" in msg.text
    assert f"Today is {resources.today.isoformat()}." in msg.text


def test_tool_then_answer_path(resources, statics):
    script = [
        {"function_call": _call(order_id="ord_3006")},
        _final("Your next payment on ord_3006 is $118.36, due 2026-07-11."),
    ]
    result, llm = _run(resources, statics, script)
    assert result.route == "tool"
    assert result.answer.startswith("Your next payment on ord_3006")
    assert len(llm.requests) == 2
    second = llm.requests[1]
    # Call #2: tool mode NONE, history = user msg, raw model turn (unchanged), tool result.
    assert second.tool_mode == "none"
    user, model_turn, tool_result = second.contents
    assert isinstance(user, UserMessage)
    assert isinstance(model_turn, ModelTurn)
    assert model_turn.raw["fake_step"] == 0
    assert isinstance(tool_result, ToolResult)
    assert tool_result.response["status"] == "ok"
    assert [o["order_id"] for o in tool_result.response["orders"]] == ["ord_3006"]
    assert [c.purpose for c in result.trace.llm_calls] == ["initial", "post_tool"]
    (record,) = result.trace.tool_calls
    assert record.to_dict() == {
        "name": "get_my_orders",
        "args": {"order_id": "ord_3006"},
        "result_status": "ok",
        "n_orders": 1,
    }


def test_call_two_uses_tool_mode_none(resources, statics):
    script = [{"function_call": _call()}, _final("You have two orders on file.")]
    _, llm = _run(resources, statics, script)
    assert [r.tool_mode for r in llm.requests] == ["auto", "none"]


def test_tool_is_bound_to_case_user(resources, statics):
    # u002 asking for a u001 order gets not_found (closure-bound user_id, SEC-01/SEC-03).
    script = [
        {"function_call": _call(order_id="ord_3001")},
        _final("I couldn't find ord_3001 on your account."),
    ]
    result, llm = _run(resources, statics, script, question="What about ord_3001?")
    assert llm.requests[1].contents[2].response == {
        "status": "not_found",
        "today": resources.today.isoformat(),
        "orders": [],
    }
    assert result.trace.tool_calls[0].result_status == "not_found"


# --- one tool round only -------------------------------------------------------------------


def test_second_tool_call_is_ignored_and_recorded(resources, statics):
    script = [
        {"function_calls": [_call(order_id="ord_3006"), _call(order_id="ord_3005")]},
        _final("Your Nordic Kicks order ord_3006 is active."),
    ]
    result, llm = _run(resources, statics, script)
    first, second = result.trace.tool_calls
    assert first.result_status == "ok" and first.args == {"order_id": "ord_3006"}
    assert second.result_status == "rejected" and second.reason == "extra_call"
    assert second.args == {"order_id": "ord_3005"}
    replies = [c for c in llm.requests[1].contents if isinstance(c, ToolResult)]
    assert replies[0].response["status"] == "ok"
    # The ignored call gets a data-free reply (keeps call/response pairing well-formed).
    assert replies[1].response["status"] == "rejected"
    assert "orders" not in replies[1].response
    assert result.route == "tool"


def test_unknown_tool_is_rejected_but_registered_call_runs(resources, statics):
    script = [
        {"function_calls": [_call("delete_orders"), _call(order_id="ord_3006")]},
        _final("Your order ord_3006 is active."),
    ]
    result, _ = _run(resources, statics, script)
    unknown, real = result.trace.tool_calls
    assert unknown.reason == "unknown_tool" and unknown.result_status == "rejected"
    assert real.result_status == "ok"
    assert result.trace.route_inputs["tool_executed"] is True


def test_model_supplied_user_id_is_never_honoured(resources, statics):
    script = [
        {"function_call": _call(order_id="ord_3001", user_id="u001")},
        _final("I can only look up your own orders."),
    ]
    result, llm = _run(resources, statics, script)
    (record,) = result.trace.tool_calls
    assert record.result_status == "rejected" and record.reason == "invalid_args"
    assert result.trace.route_inputs["tool_executed"] is False
    # Not executed → malformed_output → the repair call (tool mode none).
    assert [c.purpose for c in result.trace.llm_calls] == ["initial", "repair"]
    assert llm.requests[1].tool_mode == "none"
    reply = llm.requests[1].contents[-1]
    assert isinstance(reply, ToolResult) and reply.response["status"] == "rejected"
    assert "ord_3001" not in str(llm.requests[1].contents[-1].response)
    assert result.trace.repair_attempted
    assert result.route == "policy"


def test_post_tool_function_call_goes_to_repair(resources, statics):
    # Mode NONE should make this impossible; if a provider ignores it we never run a 2nd tool.
    script = [
        {"function_call": _call()},
        {"function_call": _call(order_id="ord_3005")},
        _final("Your Nordic Kicks order ord_3006 is active."),
    ]
    result, llm = _run(resources, statics, script)
    assert [c.purpose for c in result.trace.llm_calls] == ["initial", "post_tool", "repair"]
    assert [t.result_status for t in result.trace.tool_calls] == ["ok", "rejected"]
    assert result.answer == "Your Nordic Kicks order ord_3006 is active."
    assert all(r.tool_mode == "none" for r in llm.requests[1:])


# --- validation, repair, safe failure ------------------------------------------------------


def test_repair_path_recovers(resources, statics):
    script = [
        _final("I've waived your late fee."),
        _final("Late fees can't be waived by me; our support team can review it."),
    ]
    result, llm = _run(resources, statics, script, question="Is there a late fee?")
    assert result.answer.startswith("Late fees can't be waived by me")
    assert result.trace.repair_attempted
    assert [c.purpose for c in result.trace.llm_calls] == ["initial", "repair"]
    repair = llm.requests[1]
    assert repair.tool_mode == "none"
    assert isinstance(repair.contents[-2], ModelTurn)
    note = repair.contents[-1]
    assert isinstance(note, UserMessage) and "action_claim" in note.text
    stages = {(v["check"], v["stage"], v["verdict"]) for v in result.trace.validator}
    assert ("action_claim", "initial", "fail") in stages
    assert ("action_claim", "repair", "pass") in stages
    assert result.error_class is None


def test_repair_then_safe_failure(resources, statics):
    script = [_final("I've waived your late fee."), _final("We have refunded your order.")]
    result, llm = _run(resources, statics, script, question="Is there a late fee?")
    assert result.answer == SAFE_FAILURE_ANSWER
    assert result.route == "escalate"
    assert result.error_class == "validation_exhausted"
    assert result.trace.safe_failure
    assert len(llm.requests) == 2


def test_malformed_text_goes_to_repair(resources, statics):
    script = [{"text": "not json at all"}, _final("Pay in 4 splits a purchase in four.")]
    result, _ = _run(resources, statics, script)
    assert result.answer == "Pay in 4 splits a purchase in four."
    assert result.trace.llm_calls[0].outcome == "malformed"
    assert result.trace.repair_attempted


def test_at_most_three_semantic_calls(resources, statics):
    script = [
        {"function_call": _call()},
        _final("I've rescheduled your payment."),
        _final("I've rescheduled your payment."),
    ]
    result, llm = _run(resources, statics, script)
    assert len(llm.requests) == MAX_SEMANTIC_CALLS_PER_CASE == 3
    assert result.error_class == "validation_exhausted"


def test_semantic_calls_respect_attempt_cap(resources, statics):
    script = [{"error": "server_5xx"}, _final("You have two orders.")]
    result, _ = _run(resources, statics, script)
    for call in result.trace.llm_calls:
        assert len(call.attempts) <= resources.settings.max_attempts
    assert [a["status"] for a in result.trace.llm_calls[0].attempts] == ["retry", "ok"]


# --- tripwire wiring -----------------------------------------------------------------------


def test_fraud_mode_withholds_the_tool(resources, statics):
    script = [
        {"function_call": _call()},
        _final(
            "Please change your password and contact our fraud team, a specialist will help.",
            escalation="fraud",
        ),
    ]
    result, llm = _run(resources, statics, script, question="Someone hacked my account.")
    assert llm.requests[0].tools == ()
    assert result.trace.tripwire["fraud_mode"] is True
    (record,) = result.trace.tool_calls
    assert record.result_status == "rejected" and record.reason == "unknown_tool"
    assert result.trace.route_inputs["tool_executed"] is False
    assert result.route == "escalate"


def test_tripwire_adds_note_but_model_writes_answer(resources, statics):
    text = "I'm sorry to hear that. A specialist on our team can discuss hardship options."
    result, llm = _run(resources, statics, [_final(text)], question="I lost my job.")
    assert "human follow-up (hardship)" in llm.requests[0].contents[0].text
    assert result.answer == text
    assert result.route == "escalate"
    assert result.trace.route_inputs["forced_reason"] == "hardship"


def test_forced_escalation_without_handoff_is_repaired(resources, statics):
    script = [
        _final("Sorry to hear that."),
        _final("Sorry to hear that. I'm connecting you with a specialist."),
    ]
    result, _ = _run(resources, statics, script, question="I lost my job.")
    assert result.trace.repair_attempted
    assert result.answer.endswith("specialist.")


def test_input_guard_truncation_is_traced(resources, statics):
    long_question = "x" * (resources.settings.input_char_cap + 50)
    result, llm = _run(resources, statics, [_final("ok")], question=long_question)
    assert result.trace.to_dict()["input_truncated"] is True
    assert "x" * (resources.settings.input_char_cap + 1) not in llm.requests[0].contents[0].text


# --- consumption caps (SEC-07) -------------------------------------------------------------


def test_batch_budget_exhaustion_mid_case(resources, statics):
    budget = CallBudget(1)
    script = [{"function_call": _call()}, _final("unused")]
    result, llm = _run(resources, statics, script, budget=budget)
    assert len(llm.requests) == 1
    assert result.answer == SAFE_FAILURE_ANSWER
    assert result.error_class == "batch_limit"


def test_batch_budget_counts_semantic_calls(resources, statics):
    budget = CallBudget(10)
    script = [{"function_call": _call()}, _final("You have two orders.")]
    _run(resources, statics, script, budget=budget)
    assert budget.used == 2


def test_tokens_and_model_are_traced(resources, statics):
    script = [
        {"function_call": _call(), "usage": {"input": 100, "output": 5, "cached": 80}},
        {**_final("You have two orders."), "usage": {"input": 150, "output": 20, "cached": 80}},
    ]
    result, _ = _run(resources, statics, script)
    assert result.trace.tokens == {"input": 250, "output": 25, "cached": 160, "thoughts": 0}
    assert result.trace.model == "fake-primary"
    assert result.trace.fallback_used is False
