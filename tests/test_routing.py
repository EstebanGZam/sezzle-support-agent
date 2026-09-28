"""Route derivation (architecture §6, SEZ-C04) — unit table plus the loop wiring (FakeLLM)."""

import pytest

from support_agent.agent import AgentStatics, Case, answer_case
from support_agent.config import Settings
from support_agent.llm import FakeLLM
from support_agent.resources import Resources
from support_agent.routing import ROUTES, derive_route, ensure_route


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


# --- the pure rule -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("forced", "escalation", "tool_executed", "policy_applied", "expected"),
    [
        # the four routes
        (None, "none", False, False, "policy"),
        (None, "none", True, False, "tool"),
        (None, "none", True, True, "both"),
        (None, "dispute", False, False, "escalate"),
        # policy_applied without a tool run is still a policy answer
        (None, "none", False, True, "policy"),
        # model escalation beats the tool split
        (None, "fee_dispute", True, True, "escalate"),
        (None, "other", True, False, "escalate"),
        # forced_reason precedence over every model field
        ("fraud", "none", False, False, "escalate"),
        ("hardship", "none", True, True, "escalate"),
        ("human_only_action", "none", True, False, "escalate"),
        ("human_requested", "none", False, True, "escalate"),
        ("hardship", "hardship", False, False, "escalate"),
    ],
)
def test_derive_route_table(forced, escalation, tool_executed, policy_applied, expected):
    route = derive_route(
        forced_reason=forced,
        escalation_reason=escalation,
        tool_executed=tool_executed,
        policy_applied=policy_applied,
    )
    assert route == expected
    assert route in ROUTES


def test_routes_enum_is_exactly_the_contract():
    assert set(ROUTES) == {"policy", "tool", "both", "escalate"}


@pytest.mark.parametrize("bad", ["", "Policy", "tools", "human", "escalation"])
def test_ensure_route_rejects_non_enum_values(bad):
    with pytest.raises(ValueError):
        ensure_route(bad)


# --- the loop feeds the rule from real signals ---------------------------------------------


def _run(resources, statics, script, question, user_id="u002"):
    llm = FakeLLM(script)
    case = Case(id="r1", user_id=user_id, question=question)
    return answer_case(resources, llm, case, statics=statics), llm


def test_loop_policy_route_without_tool(resources, statics):
    result, _ = _run(
        resources, statics, [_final("Pay in 4 splits a purchase into four payments.")], "How?"
    )
    assert result.route == "policy"
    assert result.trace.route_inputs == {
        "forced_reason": None,
        "escalation_reason": "none",
        "tool_executed": False,
        "policy_applied": False,
    }


def test_loop_tool_route_uses_actual_tool_execution(resources, statics):
    script = [
        {"function_call": {"name": "get_my_orders", "args": {"merchant": "Nordic"}}},
        _final("Your Nordic Kicks order ord_3006 has one installment left."),
    ]
    result, _ = _run(resources, statics, script, "When is my next payment?")
    assert result.route == "tool"
    assert result.trace.route_inputs["tool_executed"] is True


def test_loop_both_route_uses_policy_applied(resources, statics):
    script = [
        {"function_call": {"name": "get_my_orders", "args": {"order_id": "ord_3006"}}},
        _final("Your first reschedule on ord_3006 is free.", policy_applied=True, cited=["POL-02"]),
    ]
    result, _ = _run(resources, statics, script, "Can I move my payment?")
    assert result.route == "both"
    assert result.trace.policy_applied is True


def test_loop_not_found_still_counts_as_tool_executed(resources, statics):
    # A-08: a not_found lookup is a tool run.
    script = [
        {"function_call": {"name": "get_my_orders", "args": {"order_id": "ord_999999"}}},
        _final("I couldn't find that order on your account."),
    ]
    result, _ = _run(resources, statics, script, "Where is ord_999999?")
    assert result.trace.tool_calls[0].result_status == "not_found"
    assert result.route == "tool"


def test_loop_model_escalation_routes_escalate(resources, statics):
    script = [_final("A Sezzle specialist will review this with you.", escalation="dispute")]
    result, _ = _run(resources, statics, script, "Something is wrong with my item.")
    assert result.route == "escalate"


def test_loop_forced_reason_overrides_model_fields(resources, statics):
    # The tripwire fires (explicit human request); the model says "none" and applied policy.
    script = [
        {"function_call": {"name": "get_my_orders", "args": {}}},
        _final(
            "Here is your order summary; a specialist from our team will follow up.",
            escalation="none",
            policy_applied=True,
            cited=["POL-01"],
        ),
    ]
    result, _ = _run(resources, statics, script, "Transfer me to a human agent, please.")
    assert result.trace.route_inputs["forced_reason"] == "human_requested"
    assert result.trace.route_inputs["escalation_reason"] == "none"
    assert result.trace.route_inputs["tool_executed"] is True
    assert result.route == "escalate"


def test_model_cannot_write_route(resources, statics):
    # A "route" key in the model output violates the schema (extra="forbid"); repair, then fail.
    bad = {"final": {**_final("ok")["final"], "route": "tool"}}
    result, llm = _run(resources, statics, [bad, bad], "How does it work?")
    assert result.route == "escalate"
    assert result.error_class == "validation_exhausted"
    assert len(llm.requests) == 2
