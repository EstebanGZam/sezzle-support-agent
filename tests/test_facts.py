import datetime
import re
import time
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

import support_agent
from support_agent.config import Settings
from support_agent.facts import OrderFacts, business_days_between, compute_facts
from support_agent.resources import OrdersRepository

TODAY = date(2026, 7, 1)
# A system clock far away from the data's ``today``; facts must not notice it.
PATCHED_EPOCH = datetime.datetime(2031, 3, 14, 12, tzinfo=datetime.UTC).timestamp()


@pytest.fixture(autouse=True)
def patched_clock(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: PATCHED_EPOCH)
    assert date.today() == date(2031, 3, 14)  # the patch is effective


@pytest.fixture(scope="module")
def repo():
    return OrdersRepository.from_file(Settings.from_env({"LLM_PROVIDER": "fake"}).orders_path)


def facts_for(repo, order_id, today=TODAY) -> OrderFacts:
    order = next(o for o in repo.orders if o.order_id == order_id)
    return compute_facts(order, today)


def test_next_upcoming_installment(repo):
    facts = facts_for(repo, "ord_3006")
    nxt = facts.next_upcoming_installment
    assert (nxt.installment, nxt.amount, nxt.due_date) == (4, 118.36, date(2026, 7, 11))
    assert nxt.days_until_due == 10
    assert facts.unpaid_balance == 118.36
    assert facts.days_since_order == 32
    assert facts.failed_installments == ()
    assert facts.paused_installments == ()
    assert facts.refund is None


def test_failed_is_not_upcoming_and_counts_as_unpaid(repo):
    facts = facts_for(repo, "ord_3002")
    assert facts.failed_installments == (2,)
    assert facts.next_upcoming_installment.installment == 3
    assert facts.next_upcoming_installment.days_until_due == 22
    assert [u.installment for u in facts.upcoming_installments] == [3, 4]
    assert facts.unpaid_balance == 169.24  # 56.41 (failed) + 56.41 + 56.42


def test_paused_is_not_upcoming(repo):
    facts = facts_for(repo, "ord_3001")
    assert facts.paused_installments == (3, 4)
    assert facts.next_upcoming_installment is None
    assert facts.upcoming_installments == ()
    assert facts.unpaid_balance == 73.87


def test_fully_paid_order(repo):
    facts = facts_for(repo, "ord_3003")
    assert facts.unpaid_balance == 0.0
    assert facts.next_upcoming_installment is None


@pytest.mark.parametrize(
    ("order_id", "business_days"),
    [
        ("ord_3003", 1),  # issued Tue 06-30
        ("ord_3014", 3),  # issued Sun 06-28 -> Mon, Tue, Wed
        ("ord_3009", 4),  # issued Thu 06-25 -> Fri, Mon, Tue, Wed
        ("ord_3023", 8),  # issued Sat 06-20
    ],
)
def test_refund_business_days_since_issued(repo, order_id, business_days):
    assert facts_for(repo, order_id).refund.business_days_since_issued == business_days


def test_business_days_are_monday_to_friday():
    friday, saturday, sunday, monday = (date(2026, 7, d) for d in (3, 4, 5, 6))
    assert business_days_between(friday, saturday) == 0
    assert business_days_between(friday, sunday) == 0
    assert business_days_between(friday, monday) == 1
    assert business_days_between(monday, monday) == 0
    assert business_days_between(monday, date(2026, 7, 13)) == 5
    assert business_days_between(monday, friday) == -1


def test_facts_depend_on_the_given_today_only(repo):
    later = facts_for(repo, "ord_3006", today=date(2026, 7, 8))
    assert later.next_upcoming_installment.days_until_due == 3
    assert later.days_since_order == 39
    assert facts_for(repo, "ord_3006") == facts_for(repo, "ord_3006")


def test_facts_are_json_serialisable_and_frozen(repo):
    facts = facts_for(repo, "ord_3009")
    dumped = facts.model_dump(mode="json")
    assert dumped["next_upcoming_installment"]["due_date"] == "2026-07-05"
    assert dumped["refund"] == {"business_days_since_issued": 4}
    with pytest.raises(ValidationError):
        facts.unpaid_balance = 0.0


def test_facts_hold_no_policy_conclusions():
    # ADR-1 / AR-04: neutral facts only; conclusion-style fields belong to the model.
    fields = set(OrderFacts.model_fields)
    for banned in ("eligible", "fee", "late", "escalat", "reschedulable", "can_", "allowed"):
        assert not any(banned in name for name in fields), banned


@pytest.mark.parametrize("module", ["resources.py", "facts.py"])
def test_no_system_clock_in_data_modules(module):
    source = (Path(support_agent.__file__).parent / module).read_text()
    assert not re.search(r"\.today\(|\.now\(|utcnow|time\.time", source)
