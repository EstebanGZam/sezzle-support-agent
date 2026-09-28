"""OutputValidator (SEC-06, security §4): every required must-pass / must-fail fixture plus the
remaining rows of the typed-claim table. Answers are synthetic; data comes from the real files."""

import pytest

from support_agent.config import Settings
from support_agent.guards import CHECKS, OutputValidator, ValidationContext
from support_agent.llm.base import ANSWER_MAX_CHARS, FinalAnswer
from support_agent.resources import OrdersRepository, PolicyCorpus
from support_agent.tools import build_toolset

CALLER = "u001"  # owns ord_3001 (dispute_open, paused installments) .. ord_3004
OTHER_USERS_ORDER = "ord_3006"  # belongs to u002


@pytest.fixture(scope="module")
def settings():
    return Settings.from_env({"LLM_PROVIDER": "fake"})


@pytest.fixture(scope="module")
def repo(settings):
    return OrdersRepository.from_file(settings.orders_path)


@pytest.fixture(scope="module")
def validator(settings):
    return OutputValidator(PolicyCorpus.from_dir(settings.policies_dir))


def _tool(repo, **args):
    return build_toolset(CALLER, repo, repo.today).execute("get_my_orders", args)


def _ctx(repo, message="question", **kwargs):
    return ValidationContext.for_case(repo, CALLER, message, **kwargs)


def _answer(text, reason="none", applied=False, cited=()):
    return FinalAnswer(
        answer=text,
        escalation_reason=reason,
        policy_applied=applied,
        cited_policies=list(cited),
    )


def _run(validator, ctx, text, **kwargs):
    return validator.validate(_answer(text, **kwargs), ctx)


# --- Required must-pass fixtures (security §4) ----------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Each installment is 25% of the order total.",
        "Installments are charged every two weeks.",
        "You can request this within 14 days.",
        "Turn on 2FA to keep your account secure.",
        "Refunds usually take 3–10 business days to reach your bank.",
        "I can't waive this fee, but a support specialist can review it.",
    ],
)
def test_must_pass_plain_answers(validator, repo, text):
    result = _run(validator, _ctx(repo), text)
    assert result.ok, result.to_trace()
    assert result.failures == ()


def test_must_pass_paused_installments_with_paused_data(validator, repo):
    ctx = _ctx(repo, tool_result=_tool(repo, order_id="ord_3001"))
    for text in (
        "Your installments are paused while the dispute is investigated.",
        "Your installments have been paused while the dispute is investigated.",
    ):
        result = _run(validator, ctx, text)
        assert result.ok, result.to_trace()
        assert result.verdict_of("action_claim") == "pass"


def test_must_pass_user_typed_not_found_order_id_is_a_warning(validator, repo):
    message = "Where is my order ord_9999?"
    tool_result = _tool(repo, order_id="ord_9999")
    assert tool_result["status"] == "not_found"
    ctx = _ctx(repo, message, tool_result=tool_result)
    result = _run(validator, ctx, "I couldn't find ord_9999 on your account.")
    assert result.ok, result.to_trace()
    assert result.verdict_of("order_id") == "warn"


# --- Required must-fail fixtures (security §4) ----------------------------------------------


@pytest.mark.parametrize(
    ("text", "check"),
    [
        ("I've rescheduled your payment to next month.", "action_claim"),
        ("Good news: your fee has been waived.", "action_claim"),
        ("We moved your due date by two weeks.", "action_claim"),
        ("I'll waive the fee for you this time.", "commitment"),
        ("Your limit is $500.", "limit_disclosure"),
        ("That item costs $73.19 in total.", "amount_ungrounded"),
    ],
)
def test_must_fail_fixtures(validator, repo, text, check):
    result = _run(validator, _ctx(repo, tool_result=_tool(repo)), text)
    assert not result.ok
    assert result.verdict_of(check) == "fail", result.to_trace()
    assert check in result.failure_summary()


def test_must_fail_foreign_order_id_not_typed_by_the_shopper(validator, repo):
    ctx = _ctx(repo, "When is my next payment?", tool_result=_tool(repo))
    result = _run(validator, ctx, f"Your order {OTHER_USERS_ORDER} has a payment due soon.")
    assert result.verdict_of("order_id") == "fail"
    assert not result.ok


# --- Other rows of the table ----------------------------------------------------------------


def test_every_check_is_recorded_in_order_for_the_trace(validator, repo):
    result = _run(validator, _ctx(repo), "Sezzle splits purchases into installments.")
    assert tuple(v["check"] for v in result.to_trace()) == CHECKS
    assert all(set(v) == {"check", "verdict", "detail"} for v in result.to_trace())
    assert all(v["verdict"] == "pass" for v in result.to_trace())


@pytest.mark.parametrize(
    "raw",
    [
        None,
        {"answer": "", "escalation_reason": "none", "policy_applied": False, "cited_policies": []},
        {
            "answer": "   ",
            "escalation_reason": "none",
            "policy_applied": False,
            "cited_policies": [],
        },
        {
            "answer": "x" * (ANSWER_MAX_CHARS + 1),
            "escalation_reason": "none",
            "policy_applied": False,
            "cited_policies": [],
        },
        {
            "answer": "ok",
            "escalation_reason": "urgent",
            "policy_applied": False,
            "cited_policies": [],
        },
        {"answer": "ok", "escalation_reason": "none"},
    ],
)
def test_schema_failures_stop_validation(validator, repo, raw):
    result = validator.validate(raw, _ctx(repo))
    assert result.answer is None and not result.ok
    assert [v.check for v in result.verdicts] == ["schema"]
    assert result.verdict_of("schema") == "fail"


def test_schema_accepts_a_valid_mapping(validator, repo):
    raw = {
        "answer": "ok",
        "escalation_reason": "none",
        "policy_applied": False,
        "cited_policies": [],
    }
    assert validator.validate(raw, _ctx(repo)).ok


def test_citation_drops_unknown_ids_and_warns(validator, repo):
    result = _run(validator, _ctx(repo), "ok", applied=True, cited=["POL-01", "POL-99"])
    assert result.answer.cited_policies == ["POL-01"]
    assert result.verdict_of("citation") == "warn"
    assert result.ok  # warn never triggers repair


def test_citation_warns_when_policy_applied_without_valid_citation(validator, repo):
    result = _run(validator, _ctx(repo), "ok", applied=True, cited=[])
    assert result.verdict_of("citation") == "warn"
    assert _run(validator, _ctx(repo), "ok", applied=True, cited=["POL-02"]).verdict_of(
        "citation"
    ) == ("pass")


def test_own_order_id_passes(validator, repo):
    result = _run(validator, _ctx(repo, tool_result=_tool(repo)), "Your order ord_3002 is active.")
    assert result.verdict_of("order_id") == "pass"


def test_typed_foreign_id_fails_when_the_tool_did_not_return_not_found(validator, repo):
    ctx = _ctx(repo, f"What about {OTHER_USERS_ORDER}?")  # no tool call
    result = _run(validator, ctx, f"I couldn't find {OTHER_USERS_ORDER} on your account.")
    assert result.verdict_of("order_id") == "fail"


def test_fraud_mode_blocks_any_order_id_merchant_or_caller_amount(validator, repo):
    order = repo.orders_for(CALLER)[0]
    ctx = _ctx(repo, "Someone used my card.", fraud_mode=True, forced_reason="fraud")
    for text in (
        f"I see {order.order_id} on your account; a specialist will review it.",
        f"I see a purchase at {order.merchant}; a specialist will review it.",
    ):
        assert _run(validator, ctx, text, reason="fraud").verdict_of("order_id") == "fail"
    amount = f"${order.installments[0].amount:.2f}"
    result = _run(validator, ctx, f"A charge of {amount} was made; our team will help.")
    assert result.verdict_of("amount_ungrounded") == "fail"


def test_amounts_grounded_in_tool_result_or_corpus_pass(validator, repo):
    tool_result = _tool(repo, order_id="ord_3002")
    installment = tool_result["orders"][0]["installments"][-1]["amount"]
    text = f"Your next installment is ${installment:.2f}; a failed payment fee is $10."
    result = _run(validator, _ctx(repo, tool_result=tool_result), text)
    assert result.verdict_of("amount_ungrounded") == "pass", result.to_trace()


def test_dates_outside_tool_result_only_warn(validator, repo):
    tool_result = _tool(repo, order_id="ord_3002")
    due = tool_result["orders"][0]["installments"][-1]["due_date"]
    ctx = _ctx(repo, tool_result=tool_result)
    assert _run(validator, ctx, f"It is due on {due}.").verdict_of("date_ungrounded") == "pass"
    assert _run(validator, ctx, "Today is July 1, 2026.").verdict_of("date_ungrounded") == "pass"
    result = _run(validator, ctx, "After moving it, the new due date is August 30, 2026.")
    assert result.verdict_of("date_ungrounded") == "warn"
    assert result.ok


@pytest.mark.parametrize(
    "text",
    [
        "I haven't changed anything on your order.",
        "I can't reschedule payments, but you can do it in the app.",
        "We cannot waive fees; our support team can review your case.",
    ],
)
def test_negated_actions_and_promises_pass(validator, repo, text):
    result = _run(validator, _ctx(repo), text)
    assert result.verdict_of("action_claim") == "pass"
    assert result.verdict_of("commitment") == "pass"


def test_paused_claim_without_paused_data_fails(validator, repo):
    ctx = _ctx(repo, tool_result=_tool(repo, order_id="ord_3002"))
    result = _run(validator, ctx, "Your payments have been paused.")
    assert result.verdict_of("action_claim") == "fail"


@pytest.mark.parametrize(
    "text",
    [
        "We will increase your limit next week.",
        "I can refund you today.",
        "We'll pause your payments.",
    ],
)
def test_commitments_to_human_only_outcomes_fail(validator, repo, text):
    assert _run(validator, _ctx(repo), text).verdict_of("commitment") == "fail"


def test_limit_disclosure_catches_amount_presented_as_limit(validator, repo):
    assert _run(validator, _ctx(repo), "You have a $750 spending limit.").verdict_of(
        "limit_disclosure"
    ) == ("fail")
    general = "Spending limits depend on your payment history; a specialist can review yours."
    assert _run(validator, _ctx(repo), general).verdict_of("limit_disclosure") == "pass"


def test_escalation_coherence_requires_a_handoff(validator, repo):
    no_handoff = "Please check your bank statement."
    handoff = "I'm passing this to our support team for review."
    assert _run(validator, _ctx(repo), no_handoff, reason="dispute").verdict_of(
        "escalation_coherence"
    ) == ("fail")
    assert _run(validator, _ctx(repo), handoff, reason="dispute").verdict_of(
        "escalation_coherence"
    ) == ("pass")
    forced = _ctx(repo, forced_reason="hardship")
    assert _run(validator, forced, no_handoff).verdict_of("escalation_coherence") == "fail"
    assert _run(validator, _ctx(repo), no_handoff).verdict_of("escalation_coherence") == "pass"


# --- R-01 regressions: validator false negatives / false positive ---------------------------


def test_fraud_mode_blocks_a_merchant_the_shopper_typed(validator, repo):
    """SEC-11: no caller merchant in a fraud answer, even one named in the question (R-01 #1)."""
    merchant = repo.orders_for(CALLER)[0].merchant
    message = f"I didn't authorize this order from {merchant}"
    ctx = _ctx(repo, message, fraud_mode=True, forced_reason="fraud")
    leak = f"Your {merchant} order is being escalated to a support specialist."
    assert _run(validator, ctx, leak, reason="fraud").verdict_of("order_id") == "fail"
    safe = "I'm escalating this to a support specialist who will review the unauthorized charge."
    result = _run(validator, ctx, safe, reason="fraud")
    assert result.ok, result.to_trace()


@pytest.mark.parametrize(
    "text",
    [
        f"{OTHER_USERS_ORDER} exists on another shopper's account.",
        f"{OTHER_USERS_ORDER} is active.",
        f"{OTHER_USERS_ORDER} belongs to another account.",
        f"I couldn't find {OTHER_USERS_ORDER} on your account, but it exists elsewhere.",
        f"I couldn't find {OTHER_USERS_ORDER} on your account; {OTHER_USERS_ORDER} is active.",
    ],
)
def test_typed_not_found_id_outside_a_not_found_statement_fails(validator, repo, text):
    """The echo exception needs a not-found construction; existence/ownership/status fail
    (security §4, R-01 #2)."""
    tool_result = _tool(repo, order_id=OTHER_USERS_ORDER)
    assert tool_result["status"] == "not_found"
    ctx = _ctx(repo, f"What's the status of {OTHER_USERS_ORDER}?", tool_result=tool_result)
    assert _run(validator, ctx, text).verdict_of("order_id") == "fail", text


@pytest.mark.parametrize(
    "text",
    [
        f"I couldn't find {OTHER_USERS_ORDER} on your account.",
        f"{OTHER_USERS_ORDER} doesn't appear on your account.",
        f"There is no order {OTHER_USERS_ORDER} on your account. Please double-check the ID.",
        f"I wasn't able to locate order {OTHER_USERS_ORDER} in your orders.",
    ],
)
def test_typed_not_found_id_inside_a_not_found_statement_warns(validator, repo, text):
    tool_result = _tool(repo, order_id=OTHER_USERS_ORDER)
    ctx = _ctx(repo, f"What's the status of {OTHER_USERS_ORDER}?", tool_result=tool_result)
    result = _run(validator, ctx, text)
    assert result.verdict_of("order_id") == "warn", result.to_trace()
    assert result.ok


@pytest.mark.parametrize(
    "text",
    [
        "No human or specialist is needed; I will not escalate this.",
        "No specialist is needed.",
        "I will not escalate this.",
        "Do not escalate.",
        "An agent is not needed.",
        "There's no need for a specialist to review it.",
    ],
)
def test_escalation_coherence_rejects_negated_handoffs(validator, repo, text):
    """A hand-off must be affirmative; negated forms contradict the escalation (R-01 #3)."""
    result = _run(validator, _ctx(repo), text, reason="fraud")
    assert result.verdict_of("escalation_coherence") == "fail", text


@pytest.mark.parametrize(
    "text",
    [
        "I'm passing this to our support team for review.",
        "A specialist will review your case.",
        "I've escalated this to our fraud team.",
        "I'm connecting you with a specialist.",
        "I can't waive this fee, but a support specialist can review it.",
        "Our support team will contact you shortly.",
    ],
)
def test_escalation_coherence_accepts_affirmative_handoffs(validator, repo, text):
    result = _run(validator, _ctx(repo), text, reason="fraud")
    assert result.verdict_of("escalation_coherence") == "pass", text


@pytest.mark.parametrize(
    "text",
    [
        "I opened the policy page to explain the dispute timeline.",
        "I moved the details into a list for you.",
        "I've opened your account settings page to check.",
    ],
)
def test_harmless_uses_of_ambiguous_action_verbs_pass(validator, repo, text):
    """Ambiguous verbs fail only with an account object (R-01 #6)."""
    result = _run(validator, _ctx(repo), text)
    assert result.verdict_of("action_claim") == "pass", result.to_trace()
    assert result.ok


@pytest.mark.parametrize(
    "text",
    [
        "I opened a dispute for your order.",
        "I removed the late fee.",
        "I increased your limit.",
        "I opened your case.",
        "I've rescheduled your payment.",
        "We credited the refund yesterday.",
    ],
)
def test_account_actions_with_ambiguous_or_direct_verbs_fail(validator, repo, text):
    assert _run(validator, _ctx(repo), text).verdict_of("action_claim") == "fail", text
