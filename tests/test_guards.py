import dataclasses
import json
import re

import pytest

from support_agent.config import PROJECT_ROOT, Settings
from support_agent.guards import (
    SAFE_FAILURE_ANSWER,
    InputGuard,
    Tripwire,
    TripwireResult,
)
from support_agent.resources import OrdersRepository


@pytest.fixture(scope="module")
def repo():
    return OrdersRepository.from_file(Settings.from_env({"LLM_PROVIDER": "fake"}).orders_path)


# --- InputGuard (SEC-05) --------------------------------------------------------------------


def test_input_guard_passes_clean_text(repo):
    result = InputGuard(2000, repo).check("When is my next payment?", "u001")
    assert result.text == "When is my next payment?"
    assert not result.truncated
    assert result.removed_chars == 0
    assert result.user_id_valid and result.user_known


def test_input_guard_truncates_and_flags(repo):
    result = InputGuard(10, repo).check("x" * 25, "u001")
    assert result.text == "x" * 10
    assert result.truncated
    assert result.original_length == 25


def test_input_guard_strips_control_and_format_chars(repo):
    raw = "pay\x00ment\x1b[31m due‮?​\r\nline two\tok"
    result = InputGuard(2000, repo).check(raw, "u001")
    assert result.text == "payment[31m due?\nline two\tok"
    assert result.removed_chars == 5


def test_input_guard_flags_unknown_and_malformed_users(repo):
    guard = InputGuard(2000, repo)
    unknown = guard.check("hi", "u999999")
    assert unknown.user_id_valid and not unknown.user_known
    malformed = guard.check("hi", "admin; drop")
    assert not malformed.user_id_valid and not malformed.user_known
    assert set(unknown.to_dict()) == {
        "truncated",
        "original_length",
        "removed_chars",
        "user_id_valid",
        "user_known",
    }


def test_input_guard_rejects_bad_cap():
    with pytest.raises(ValueError):
        InputGuard(0)


# --- Tripwire (SEC-09) ----------------------------------------------------------------------
# Synthetic phrasings written for these tests; none is copied from the case files (checked below).

FIRES = {
    "fraud": [
        "There is a purchase on my account that I didn't make.",
        "My card was stolen and someone is using it.",
        "Someone hacked into my account last night.",
        "I don't recognize this charge from a store I've never shopped at.",
        "I see an unauthorized transaction on my statement.",
        "I never authorized that payment.",
    ],
    "hardship": [
        "I was laid off last month and money is tight.",
        "I just lost my job, so the next installment worries me.",
        "I can't afford the remaining installments right now.",
        "We had a medical emergency in the family, so paying is hard.",
        "Our house flooded in the storm last week.",
        "I'm going through financial hardship.",
    ],
    "human_only_action": [
        "Please waive the late fee on my account.",
        "Can you remove the $10 charge from my order?",
        "What is my exact spending limit?",
        "Why did my grocery order get declined today?",
        "I need to know why this purchase got declined, tell me why my purchase was declined.",
        "I want you to file a dispute against the seller for me.",
        "Pause my payments until next month.",
        "Could you correct the late payment on my credit report?",
        "Raise my limit so I can buy this.",
        "Please override the decline on my purchase.",
        "Stop charging me until this is sorted out.",
    ],
    "human_requested": [
        "I need to talk to a real person.",
        "Transfer me to a human agent, please.",
        "Let me speak with a supervisor.",
        "Please escalate this.",
        "Connect me with a representative.",
    ],
}

DOES_NOT_FIRE = [
    "How do disputes work?",
    "Is there a fee for rescheduling?",
    "How do I open a dispute?",
    "Can you explain how disputes work?",
    "Can you explain how to pause my payments during a dispute?",
    "What happens if a payment fails?",
    "How are spending limits decided?",
    "Does Sezzle charge interest?",
    "What is the hardship program?",
    "How does Sezzle handle fraud reports?",
    "Why do orders get declined?",
    "I didn't make my payment on time, what fee applies?",
    "I have an order, and I didn't make the second payment yet.",
    "When is my next installment due?",
    "Do I need to talk to an agent to reschedule?",
    "What is the reactivation fee?",
    "Is my limit fixed or does it change?",
    "What should I do if my card is stolen?",
    "Can I reschedule my payment?",
    "How long does a refund take?",
    "Please explain the late fee.",
    "I'm experiencing difficulties logging in to the app.",
    "Can you tell me whether you can waive fees?",
    "",
]


def _cases():
    rows = []
    for path in sorted((PROJECT_ROOT / "cases").glob("*.jsonl")):
        rows += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return rows


@pytest.mark.parametrize(
    ("category", "text"), [(c, t) for c, texts in FIRES.items() for t in texts]
)
def test_tripwire_fires_on_request_phrasings(category, text):
    result = Tripwire().check(text)
    assert category in result.categories, result
    assert result.forced_reason == result.categories[0]
    assert result.fraud_mode == (category == "fraud" or "fraud" in result.categories)


@pytest.mark.parametrize("text", DOES_NOT_FIRE)
def test_tripwire_ignores_informational_questions(text):
    result = Tripwire().check(text)
    assert result.forced_reason is None, result
    assert not result.fired and not result.fraud_mode
    assert result.categories == () and result.matched_rules == ()


def test_tripwire_fraud_takes_precedence_and_sets_fraud_mode():
    text = "Someone hacked my account. I lost my job too. Transfer me to a human agent."
    result = Tripwire().check(text)
    assert result.categories == ("fraud", "hardship", "human_requested")
    assert result.forced_reason == "fraud"
    assert result.fraud_mode


def test_tripwire_handles_curly_apostrophes_and_case():
    assert Tripwire().check("I DIDN’T AUTHORIZE THIS ORDER").forced_reason == "fraud"


def test_tripwire_never_produces_answer_text():
    fields = {f.name for f in dataclasses.fields(TripwireResult)}
    assert fields == {"forced_reason", "fraud_mode", "categories", "matched_rules"}
    for texts in FIRES.values():
        for text in texts:
            result = Tripwire().check(text)
            assert result.forced_reason in {
                "fraud",
                "hardship",
                "human_only_action",
                "human_requested",
            }
            for rule in result.matched_rules:
                assert re.fullmatch(r"[a-z_]+(?:\.[a-z]+)?\[\d+\]", rule)
            assert set(result.to_dict()) == fields


def test_synthetic_phrasings_are_not_copied_from_cases():
    questions = [row["question"].casefold() for row in _cases()]
    for text in [t for texts in FIRES.values() for t in texts] + DOES_NOT_FIRE:
        if text:
            assert all(text.casefold() not in q for q in questions), text


def test_safe_failure_text_is_the_fixed_sec10_message():
    assert SAFE_FAILURE_ANSWER == (
        "I'm sorry — I can't complete this request right now. I'm connecting you with a Sezzle "
        "support specialist who can help."
    )
