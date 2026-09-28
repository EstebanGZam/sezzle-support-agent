import json
import re
from datetime import date
from pathlib import Path

import pytest

import support_agent
from support_agent.config import Settings
from support_agent.resources import OrdersRepository
from support_agent.tools import (
    GET_MY_ORDERS,
    UnknownToolError,
    build_toolset,
)

TODAY = date(2026, 7, 1)
ORDER_VIEW_KEYS = {
    "order_id",
    "merchant",
    "order_date",
    "total",
    "plan",
    "status",
    "reschedules_used",
    "refund",
    "installments",
    "facts",
}


@pytest.fixture(scope="module")
def repo():
    return OrdersRepository.from_file(Settings.from_env({"LLM_PROVIDER": "fake"}).orders_path)


def lookup(repo, user_id, today=TODAY, **args):
    return build_toolset(user_id, repo, today).execute(GET_MY_ORDERS, args)


def order_ids(payload):
    return [o["order_id"] for o in payload["orders"]]


def canonical(payload):
    return json.dumps(payload, sort_keys=True).encode()


def test_registry_is_the_single_read_only_tool(repo):
    toolset = build_toolset("u001", repo, TODAY)
    assert toolset.names == {GET_MY_ORDERS}
    assert [d["name"] for d in toolset.declarations()] == [GET_MY_ORDERS]
    for name in ("reschedule_installment", "issue_refund", "get_orders", ""):
        with pytest.raises(UnknownToolError):
            toolset.execute(name, {})


def test_schema_has_no_user_field(repo):
    (declaration,) = build_toolset("u001", repo, TODAY).declarations()
    params = declaration["parameters"]
    assert params["type"] == "object"
    assert set(params["properties"]) == {"order_id", "merchant"}
    assert "required" not in params
    assert "user" not in json.dumps(declaration).lower()


def test_declaration_is_plain_json_and_not_mutable_by_callers(repo):
    toolset = build_toolset("u001", repo, TODAY)
    declarations = toolset.declarations()
    json.dumps(declarations)
    declarations[0]["parameters"]["properties"]["user_id"] = {"type": "string"}
    assert "user_id" not in toolset.declarations()[0]["parameters"]["properties"]


def test_no_filter_returns_all_of_the_callers_orders(repo):
    payload = lookup(repo, "u001")
    assert payload["status"] == "ok"
    assert payload["today"] == "2026-07-01"
    assert order_ids(payload) == ["ord_3001", "ord_3002", "ord_3003", "ord_3004"]


def test_own_order_by_id_includes_record_and_facts(repo):
    payload = lookup(repo, "u002", order_id="ord_3006")
    assert payload["status"] == "ok"
    (view,) = payload["orders"]
    assert set(view) == ORDER_VIEW_KEYS  # no user_id, no names
    assert view["merchant"] == "Nordic Kicks"
    nxt = view["facts"]["next_upcoming_installment"]
    assert (nxt["installment"], nxt["amount"], nxt["due_date"]) == (4, 118.36, "2026-07-11")
    assert nxt["days_until_due"] == 10
    assert view["facts"]["unpaid_balance"] == 118.36


def test_facts_use_the_given_today(repo):
    payload = lookup(repo, "u002", today=date(2026, 7, 8), order_id="ord_3006")
    assert payload["today"] == "2026-07-08"
    assert payload["orders"][0]["facts"]["next_upcoming_installment"]["days_until_due"] == 3


def test_foreign_order_is_never_returned(repo):
    payload = lookup(repo, "u002", order_id="ord_3001")  # belongs to u001
    assert payload == {"status": "not_found", "today": "2026-07-01", "orders": []}


def test_foreign_and_nonexistent_ids_are_byte_identical(repo):
    foreign = lookup(repo, "u002", order_id="ord_3001")
    nonexistent = lookup(repo, "u002", order_id="ord_9999")
    malformed = lookup(repo, "u002", order_id="order 3001")
    unknown_user = lookup(repo, "u999", order_id="ord_3001")
    assert canonical(foreign) == canonical(nonexistent) == canonical(malformed)
    assert canonical(unknown_user) == canonical(foreign)
    assert "ord_3001" not in canonical(foreign).decode()


def test_foreign_merchant_is_not_found(repo):
    # "Atlas Fitness" exists only for other users.
    assert canonical(lookup(repo, "u002", merchant="Atlas Fitness")) == canonical(
        lookup(repo, "u002", merchant="No Such Store")
    )
    assert lookup(repo, "u002", merchant="Atlas Fitness")["status"] == "not_found"


def test_merchant_match_returns_all_of_the_callers_matches(repo):
    assert order_ids(lookup(repo, "u003", merchant="Bloom & Vine")) == ["ord_3007", "ord_3008"]
    assert order_ids(lookup(repo, "u001", merchant="peak threads")) == ["ord_3002", "ord_3004"]
    # Substring, case-insensitive, whitespace-tolerant; still scoped to the caller.
    assert order_ids(lookup(repo, "u003", merchant="  BLOOM  ")) == ["ord_3007", "ord_3008"]
    assert order_ids(lookup(repo, "u005", merchant="circuit")) == ["ord_3014"]


def test_order_id_and_merchant_combine(repo):
    assert order_ids(lookup(repo, "u003", order_id="ord_3008", merchant="bloom")) == ["ord_3008"]
    assert lookup(repo, "u003", order_id="ord_3009", merchant="bloom")["status"] == "not_found"


def test_unknown_user_is_not_found(repo):
    for args in ({}, {"order_id": "ord_3001"}, {"merchant": "Luma"}):
        payload = lookup(repo, "u999", **args)
        assert payload == {"status": "not_found", "today": "2026-07-01", "orders": []}


@pytest.mark.parametrize(
    "order_id",
    [
        "3006",
        "ORD_3006",
        "ord_",
        "ord_1234567",
        "ord_3006; ord_3001",
        "ord_3006\n",
        " ord_3006",
        "*",
        3006,
        ["ord_3006"],
        {"id": "ord_3006"},
    ],
)
def test_malformed_order_id_is_no_match(repo, order_id):
    payload = lookup(repo, "u002", order_id=order_id)
    assert canonical(payload) == canonical(lookup(repo, "u002", order_id="ord_9999"))


@pytest.mark.parametrize("merchant", ["x" * 61, 42, ["Nordic Kicks"]])
def test_invalid_merchant_is_no_match(repo, merchant):
    assert lookup(repo, "u002", merchant=merchant)["status"] == "not_found"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_filters_mean_no_filter(repo, blank):
    assert order_ids(lookup(repo, "u002", order_id=blank)) == ["ord_3005", "ord_3006"]
    assert order_ids(lookup(repo, "u002", merchant=blank)) == ["ord_3005", "ord_3006"]


def test_model_supplied_user_id_cannot_widen_scope(repo):
    toolset = build_toolset("u002", repo, TODAY)
    assert order_ids(toolset.execute(GET_MY_ORDERS, {"user_id": "u001"})) == [
        "ord_3005",
        "ord_3006",
    ]
    payload = toolset.execute(GET_MY_ORDERS, {"user_id": "u001", "order_id": "ord_3001"})
    assert payload["status"] == "not_found"
    assert toolset.execute(GET_MY_ORDERS, None)["status"] == "ok"


def test_closures_are_bound_per_caller(repo):
    first = build_toolset("u001", repo, TODAY)
    second = build_toolset("u008", repo, TODAY)
    assert order_ids(second.execute(GET_MY_ORDERS, {})) == ["ord_3022", "ord_3023"]
    assert order_ids(first.execute(GET_MY_ORDERS, {}))[0] == "ord_3001"


def test_every_callers_payload_is_json_serialisable_and_own_data_only(repo):
    for user in repo.users:
        payload = lookup(repo, user.user_id)
        own = {o.order_id for o in repo.orders_for(user.user_id)}
        assert set(order_ids(payload)) == own
        text = json.dumps(payload)
        assert user.name not in text
        assert all(u.user_id not in text for u in repo.users)


def test_no_system_clock_in_tools():
    source = (Path(support_agent.__file__).parent / "tools.py").read_text()
    assert not re.search(r"\.today\(|\.now\(|utcnow|time\.time", source)
