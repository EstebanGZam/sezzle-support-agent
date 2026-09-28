"""The one read-only tool, ``get_my_orders``, bound to the caller (architecture §3.2).

Authorization lives here, at the harness → tool edge (security §1): the caller's ``user_id`` is
captured by a closure and is never a tool parameter (SEC-01); orders are filtered by the caller
**before** any matching (SEC-02); and every miss — foreign order, nonexistent order, malformed
argument, unknown user — yields the same ``not_found`` payload, so the tool is no existence
oracle (SEC-03). Nothing here can change data (SEC-04).

Declarations are plain JSON-schema dicts so any LLM adapter can translate them.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

from support_agent.facts import compute_facts
from support_agent.resources import ORDER_ID_PATTERN, Order, OrdersRepository

GET_MY_ORDERS = "get_my_orders"
MERCHANT_MAX_LEN = 60

_ORDER_ID_RE = re.compile(ORDER_ID_PATTERN)
_WHITESPACE_RE = re.compile(r"\s+")

GET_MY_ORDERS_DECLARATION: Mapping[str, Any] = {
    "name": GET_MY_ORDERS,
    "description": (
        "Look up the current shopper's own Sezzle orders: recorded order fields, installments, "
        "refund, and neutral derived facts. With no arguments, returns all of the shopper's "
        "orders. Optional filters narrow the result; a filter that matches none of the "
        "shopper's orders returns status 'not_found'. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "An order ID such as 'ord_1234'.",
                "pattern": ORDER_ID_PATTERN,
            },
            "merchant": {
                "type": "string",
                "description": "A merchant name or part of it; case-insensitive.",
                "maxLength": MERCHANT_MAX_LEN,
            },
        },
    },
}

ToolExecutor = Callable[[Mapping[str, Any]], dict[str, Any]]


class UnknownToolError(LookupError):
    """The model asked for a tool that is not registered for this case."""


@dataclass(frozen=True)
class Toolset:
    """The tools registered for one case, each already bound to that case's caller."""

    _declarations: Mapping[str, Mapping[str, Any]]
    _executors: Mapping[str, ToolExecutor]

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._executors)

    def declarations(self) -> list[dict[str, Any]]:
        """Fresh copies, so callers can never alter the registered schema."""
        return [copy.deepcopy(dict(d)) for d in self._declarations.values()]

    def execute(self, name: str, args: Mapping[str, Any] | None) -> dict[str, Any]:
        executor = self._executors.get(name)
        if executor is None:
            raise UnknownToolError(name)
        return executor(args or {})


def build_toolset(user_id: str, repo: OrdersRepository, today: date) -> Toolset:
    """Register ``get_my_orders`` with ``user_id`` fixed by closure (never model-controlled)."""

    def get_my_orders(args: Mapping[str, Any]) -> dict[str, Any]:
        # Scope first (SEC-02): only the caller's orders ever reach the matching step.
        orders = repo.orders_for(user_id)
        order_id = _optional_str(args.get("order_id"))
        merchant = _optional_str(args.get("merchant"))
        if order_id is not None:
            orders = tuple(o for o in orders if _order_id_matches(o, order_id))
        if merchant is not None:
            orders = tuple(o for o in orders if _merchant_matches(o, merchant))
        if not orders:
            return not_found_payload(today)
        return {
            "status": "ok",
            "today": today.isoformat(),
            "orders": [order_view(o, today) for o in orders],
        }

    return Toolset(
        _declarations=MappingProxyType({GET_MY_ORDERS: GET_MY_ORDERS_DECLARATION}),
        _executors=MappingProxyType({GET_MY_ORDERS: get_my_orders}),
    )


def not_found_payload(today: date) -> dict[str, Any]:
    """The single miss payload; it deliberately echoes nothing from the request (SEC-03)."""
    return {"status": "not_found", "today": today.isoformat(), "orders": []}


def order_view(order: Order, today: date) -> dict[str, Any]:
    """Recorded order fields (without ``user_id``) plus neutral ``facts`` (architecture §4)."""
    view = order.model_dump(mode="json", exclude={"user_id"})
    view["facts"] = compute_facts(order, today).model_dump(mode="json")
    return view


def _optional_str(value: Any) -> Any:
    """``None`` and blank strings mean "no filter"; any other value is kept as given."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return value


def _order_id_matches(order: Order, order_id: Any) -> bool:
    # A non-string or pattern-violating ID matches nothing (architecture §3.2).
    if not isinstance(order_id, str):
        return False
    return _ORDER_ID_RE.fullmatch(order_id) is not None and order.order_id == order_id


def _merchant_matches(order: Order, merchant: Any) -> bool:
    if not isinstance(merchant, str) or len(merchant) > MERCHANT_MAX_LEN:
        return False
    return _normalise(merchant) in _normalise(order.merchant)


def _normalise(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip().casefold()
