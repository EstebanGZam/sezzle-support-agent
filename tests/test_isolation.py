"""Cross-case isolation (SEC-12, OWN-04): nothing but immutable resources is shared."""

import dataclasses
import json
import types

import pytest

import support_agent.agent as agent_module
import support_agent.routing as routing_module
import support_agent.trace as trace_module
from support_agent.agent import AgentStatics, Case, answer_case
from support_agent.config import Settings
from support_agent.llm import FakeLLM, ModelTurn, ToolResult, UserMessage
from support_agent.resources import Resources


@pytest.fixture(scope="module")
def resources():
    return Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))


@pytest.fixture(scope="module")
def statics(resources):
    return AgentStatics.build(resources)


def _final(answer, policy_applied=False):
    return {
        "final": {
            "answer": answer,
            "escalation_reason": "none",
            "policy_applied": policy_applied,
            "cited_policies": [],
        }
    }


def _identifiers(resources, user_id):
    orders = resources.orders.orders_for(user_id)
    return {o.order_id for o in orders} | {o.merchant for o in orders}


U001_CASE = Case(id="iso-1", user_id="u001", question="What's going on with my orders?")
U002_CASE = Case(id="iso-2", user_id="u002", question="When is my next payment?")
U001_STEPS = [
    {"function_call": {"name": "get_my_orders", "args": {}}},
    _final("Your ord_3001 and ord_3002 orders are on file."),
]
U002_STEPS = [
    {"function_call": {"name": "get_my_orders", "args": {}}},
    _final("Your Nordic Kicks order ord_3006 has one payment left."),
]


def test_u001_then_u002_shares_nothing(resources, statics):
    llm = FakeLLM(U001_STEPS + U002_STEPS)
    first = answer_case(resources, llm, U001_CASE, statics=statics)
    n_first = len(llm.requests)
    second = answer_case(resources, llm, U002_CASE, statics=statics)

    u001 = _identifiers(resources, "u001")
    assert u001  # sanity: u001 has orders
    # The u001 data was really used in the first case...
    assert any("ord_3001" in json.dumps(c.response) for c in llm.requests[1].contents[2:])
    assert first.trace.user_id == "u001"

    # ...and none of it reaches the u002 requests, answer or trace.
    for request in llm.requests[n_first:]:
        for content in request.contents:
            if isinstance(content, UserMessage):
                blob = content.text
            elif isinstance(content, ToolResult):
                blob = json.dumps(content.response)
            else:
                assert isinstance(content, ModelTurn)
                blob = json.dumps(content.raw)
            assert not any(ident in blob for ident in u001), blob
        assert request.contents[0].text.count("<shopper_message>") == 1
    second_trace = second.trace.to_json()
    assert not any(ident in second_trace for ident in u001)
    assert not any(ident in second.answer for ident in u001)
    assert "u001" not in second_trace


def test_result_does_not_depend_on_previous_case(resources, statics):
    alone = answer_case(resources, FakeLLM(U002_STEPS), U002_CASE, statics=statics)
    llm = FakeLLM(U001_STEPS + U002_STEPS)
    answer_case(resources, llm, U001_CASE, statics=statics)
    after = answer_case(resources, llm, U002_CASE, statics=statics)
    assert (alone.route, alone.answer) == (after.route, after.answer)
    strip = {"latency_ms", "llm_calls", "model"}
    a = {k: v for k, v in alone.trace.to_dict().items() if k not in strip}
    b = {k: v for k, v in after.trace.to_dict().items() if k not in strip}
    assert a == b


def test_each_case_gets_its_own_toolset_binding(resources, statics):
    # The same model-proposed call returns only the calling user's orders.
    call = {"function_call": {"name": "get_my_orders", "args": {}}}
    llm = FakeLLM([call, _final("Here are your orders."), call, _final("Here are your orders.")])
    answer_case(resources, llm, U001_CASE, statics=statics)
    answer_case(resources, llm, U002_CASE, statics=statics)
    first_result = llm.requests[1].contents[2].response
    second_result = llm.requests[3].contents[2].response
    assert {o["order_id"] for o in first_result["orders"]} == {
        o.order_id for o in resources.orders.orders_for("u001")
    }
    assert {o["order_id"] for o in second_result["orders"]} == {
        o.order_id for o in resources.orders.orders_for("u002")
    }


def test_shared_objects_are_immutable(resources, statics):
    # Resources, statics and prompt bundle are frozen dataclasses.
    for obj in (resources, statics, statics.prompts, resources.orders, resources.policies):
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.some_new_attr = 1


@pytest.mark.parametrize("module", [agent_module, routing_module, trace_module])
def test_no_module_level_mutable_state(module):
    mutable = (list, dict, set, bytearray)
    offenders = [
        name
        for name, value in vars(module).items()
        if not name.startswith("__")
        and isinstance(value, mutable)
        and not isinstance(value, types.MappingProxyType)
    ]
    assert offenders == []
