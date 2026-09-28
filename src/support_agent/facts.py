"""Neutral derived facts per order (architecture §4, ADR-1 boundary).

Pure functions of ``(order, today)``: date/amount arithmetic and selection only. Nothing here
applies a policy threshold or decides eligibility, fees or escalation; that is the model's job.
``today`` is always passed in (from ``data/orders.json``), never read from the clock (SEZ-F06).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from support_agent.resources import Installment, Order


class _Fact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class UpcomingInstallment(_Fact):
    installment: int
    amount: float
    due_date: date
    days_until_due: int


class RefundFacts(_Fact):
    business_days_since_issued: int


class OrderFacts(_Fact):
    # Lowest-numbered ``upcoming`` installment; ``paused`` and ``failed`` are not upcoming
    # (A-06, A-14).
    next_upcoming_installment: UpcomingInstallment | None
    upcoming_installments: tuple[UpcomingInstallment, ...]
    # Sum of every installment not ``paid`` (upcoming + failed + paused).
    unpaid_balance: float
    failed_installments: tuple[int, ...]
    paused_installments: tuple[int, ...]
    days_since_order: int
    refund: RefundFacts | None


def compute_facts(order: Order, today: date) -> OrderFacts:
    upcoming = tuple(
        _upcoming(inst, today)
        for inst in sorted(order.installments, key=lambda i: i.installment)
        if inst.status == "upcoming"
    )
    unpaid = sum(
        (Decimal(str(i.amount)) for i in order.installments if i.status != "paid"),
        Decimal("0"),
    )
    refund = (
        RefundFacts(
            business_days_since_issued=business_days_between(order.refund.issued_date, today)
        )
        if order.refund is not None
        else None
    )
    return OrderFacts(
        next_upcoming_installment=upcoming[0] if upcoming else None,
        upcoming_installments=upcoming,
        unpaid_balance=float(round(unpaid, 2)),
        failed_installments=_numbers(order, "failed"),
        paused_installments=_numbers(order, "paused"),
        days_since_order=(today - order.order_date).days,
        refund=refund,
    )


def business_days_between(start: date, end: date) -> int:
    """Mon–Fri days in ``(start, end]``, no holiday calendar (A-07); negative if ``end < start``.

    A refund issued yesterday (a weekday) is 1 business day old today.
    """
    if end < start:
        return -business_days_between(end, start)
    count = 0
    day = start + timedelta(days=1)
    while day <= end:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def _upcoming(inst: Installment, today: date) -> UpcomingInstallment:
    return UpcomingInstallment(
        installment=inst.installment,
        amount=inst.amount,
        due_date=inst.due_date,
        days_until_due=(inst.due_date - today).days,
    )


def _numbers(order: Order, status: str) -> tuple[int, ...]:
    return tuple(sorted(i.installment for i in order.installments if i.status == status))
