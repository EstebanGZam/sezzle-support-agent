"""Code guards around the model (architecture §5 steps 1, 2, 7; security §3–§5).

- ``InputGuard`` (SEC-05): strips control/format characters, caps length, checks ``user_id``.
- ``Tripwire`` (SEC-09): a precision-first, one-way escalation signal. It only sets
  ``forced_reason`` (and fraud mode); it never writes answer text. Vocabulary is generic support
  language written for this module, not taken from evaluation cases (OWN-12).
- ``OutputValidator`` (SEC-06, SEC-11): the typed-claim checks of security §4, each recorded as a
  ``pass | warn | fail`` verdict for the trace. Only ``fail`` triggers the repair call.
- ``SAFE_FAILURE_ANSWER`` (SEC-10): the only canned text in the system.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import ValidationError

from support_agent.llm.base import FinalAnswer
from support_agent.resources import USER_ID_PATTERN, Order, OrdersRepository, PolicyCorpus

SAFE_FAILURE_ANSWER = (
    "I'm sorry — I can't complete this request right now. I'm connecting you with a Sezzle "
    "support specialist who can help."
)

# --- Input guard (SEC-05) -------------------------------------------------------------------

_USER_ID_RE = re.compile(USER_ID_PATTERN)
_KEPT_CONTROLS = frozenset("\n\t")


@dataclass(frozen=True)
class GuardedInput:
    text: str
    truncated: bool
    original_length: int
    removed_chars: int
    user_id_valid: bool
    user_known: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "truncated": self.truncated,
            "original_length": self.original_length,
            "removed_chars": self.removed_chars,
            "user_id_valid": self.user_id_valid,
            "user_known": self.user_known,
        }


class InputGuard:
    """Cleans the shopper's text; an unknown user gets no special path (the tool finds nothing)."""

    def __init__(self, char_cap: int, repo: OrdersRepository | None = None) -> None:
        if char_cap < 1:
            raise ValueError("char_cap must be >= 1")
        self.char_cap = char_cap
        self.repo = repo

    def check(self, question: str, user_id: str) -> GuardedInput:
        normalised = question.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = "".join(ch for ch in normalised if _keep_char(ch))
        truncated = len(cleaned) > self.char_cap
        valid = isinstance(user_id, str) and _USER_ID_RE.fullmatch(user_id) is not None
        return GuardedInput(
            text=cleaned[: self.char_cap] if truncated else cleaned,
            truncated=truncated,
            original_length=len(question),
            # Counts every character dropped, including the "\r" of a CRLF pair.
            removed_chars=len(question) - len(cleaned),
            user_id_valid=valid,
            user_known=valid and self.repo is not None and self.repo.has_user(user_id),
        )


def _keep_char(ch: str) -> bool:
    # Cc = control characters; Cf = format characters (zero-width, bidi overrides).
    return ch in _KEPT_CONTROLS or unicodedata.category(ch) not in ("Cc", "Cf")


# --- Tripwire (SEC-09, security §3) ---------------------------------------------------------

TripwireCategory = Literal["fraud", "hardship", "human_only_action", "human_requested"]
# Highest first: fraud also switches on fraud mode, so it must win.
TRIPWIRE_PRECEDENCE: tuple[TripwireCategory, ...] = (
    "fraud",
    "hardship",
    "human_only_action",
    "human_requested",
)

_ME = r"(?:i|we)"
_MY = r"(?:my|our)"
_DET = r"(?:this|that|these|those|the|an?|any)"
# "payment" is left out on purpose: "I didn't make my payment" is a missed payment, not fraud.
_TXN = r"(?:orders?|purchases?|charges?|transactions?)"
_AGENT = (
    r"(?:real\s+|live\s+|actual\s+)?(?:human|person|agent|representative|rep|supervisor|"
    r"manager|specialist|someone|somebody)"
)

# Each category: patterns that are, on their own, explicit enough to fire.
_FRAUD = (
    # "didn't" takes the base form, "never" the past tense ("never authorized").
    rf"\b{_ME}\s+(?:did\s*not|didn't|never)\s+(?:placed?|make|made|authori[sz]ed?)\s+{_DET}\s+"
    rf"{_TXN}",
    rf"\b{_ME}\s+(?:did\s*not|didn't|never)\s+authori[sz]ed?\s+{_DET}\s+payments?",
    # "a purchase on my account that I didn't make" -- within one clause, and the verb takes no
    # object of its own ("an order, and I didn't make the payment" is not fraud).
    rf"\b{_TXN}\b(?:(?!\b(?:and|but|so)\b)[^.?!\n,]){{0,40}}?\b{_ME}\s+(?:did\s*not|didn't|"
    r"never)\s+(?:placed?|make|made|authori[sz]ed?|order(?:ed)?)\b(?!\s+(?:the|my|a|an|any|this|that|it|"
    r"payments?)\b)",
    rf"\b(?:do\s*not|don't)\s+recogni[sz]e\s+{_DET}\s+(?:{_TXN}|payments?)",
    rf"\b(?:unauthori[sz]ed|fraudulent|unrecogni[sz]ed)\s+(?:{_TXN}|payments?|activity|"
    r"log\s*ins?|access|use)",
    rf"\b{_MY}\s+(?:credit\s+|debit\s+|bank\s+)?(?:card|wallet|identity)\s+(?:was|were|has\s+"
    r"been|got)\s+(?:stolen|compromised|skimmed)",
    rf"\b(?:someone|somebody|they)\s+(?:has\s+)?stole(?:n)?\s+{_MY}\s+(?:\w+\s+)?(?:card|"
    r"identity|wallet|account)",
    r"\bvictims?\s+of\s+identity\s+theft\b",
    rf"\b(?:someone|somebody|a\s+stranger)\s+(?:else\s+)?(?:has\s+)?(?:hacked(?:\s+into)?|accessed|broke\s+"
    rf"into|got\s+into|logged\s+into|is\s+using|used|took\s+over)\s+{_MY}\s+(?:account|card)",
    rf"\b{_MY}\s+account\s+(?:was|has\s+been|got|is)\s+(?:hacked|compromised|taken\s+over)",
    rf"\b{_ME}\s+(?:was|were|got|have\s+been|'ve\s+been)\s+hacked\b",
)

_HARDSHIP = (
    rf"\b{_ME}\s+(?:just\s+|recently\s+)?(?:lost|have\s+lost|'ve\s+lost)\s+{_MY}\s+"
    r"(?:job|income|work|home|house)",
    rf"\b{_ME}\s+(?:was|were|got|have\s+been|'ve\s+been|just\s+got)\s+(?:laid\s+off|fired|let\s+go)",
    r"\b(?:i'm|i\s+am|we're|we\s+are)\s+(?:now\s+|currently\s+)?(?:unemployed|out\s+of\s+work|"
    r"between\s+jobs)",
    rf"\b{_ME}\s+(?:can't|cannot|can\s+not|won't\s+be\s+able\s+to|am\s+unable\s+to|'m\s+unable\s+"
    r"to|am\s+not\s+able\s+to|'m\s+not\s+able\s+to|could\s*n[o']?t)\s+afford\b",
    rf"\b{_ME}\s+(?:can't|cannot)\s+(?:keep\s+up\s+with|make\s+ends\s+meet)",
    r"\b(?:i'm|i\s+am|we're|we\s+are)\s+(?:going\s+through|facing|experiencing|dealing\s+with|in)"
    r"\s+(?:a\s+|some\s+)?(?:(?:financial|money)\s+(?:hardship|crisis|difficult\w*|trouble|"
    r"problems?)|hardship)",
    r"\bstruggling\s+(?:financially|with\s+money|to\s+(?:pay|make|afford|keep\s+up))",
    r"\b(?:i|we|my|our)\b[^.?!\n]{0,40}\b(?:medical|family|health)\s+emergency",
    r"\b(?:i|we|my|our)\b[^.?!\n]{0,40}\b(?:hurricane|flood(?:ed|ing)?|wildfire|earthquake|"
    r"tornado|natural\s+disaster|house\s+fire)\b",
)

# Explicit disclosure/decline-reason demands: request phrasing is built into the pattern.
_HUMAN_ONLY_DIRECT = (
    rf"\b(?:what(?:'s|\s+is)|tell\s+me|give\s+me|show\s+me|disclose|reveal|share|i\s+(?:want|need)"
    rf"\s+to\s+know)\s+{_MY}\s+(?:exact|precise|actual|real|true|specific|maximum|max)\s+"
    r"(?:spending\s+|credit\s+|order\s+)?(?:limit|spending\s+power)",
    r"\b(?:exact|precise)\s+(?:limit\s+)?formula\b",
    r"\bwhy\s+(?:was|did|were|is)\s+(?:my|this|that|the)\s+(?:\w+\s+){0,3}?(?:order|purchase|"
    r"transaction|card|payment)s?\s+(?:get\s+|being\s+)?(?:declined|denied|rejected)",
    r"\bwhy\s+(?:my|this|that|the)\s+(?:\w+\s+){0,3}?(?:order|purchase|transaction|card|payment)s?"
    r"\s+(?:was|got|is\s+being|keeps\s+getting|were)\s+(?:declined|denied|rejected)",
)

# Human-only actions; they fire only inside a sentence that is phrased as a request.
_HUMAN_ONLY_ACTIONS = (
    # Fee waiver / removal.
    r"\b(?:waive|remove|drop|cancel|refund|reverse|forgive|take\s+off|get\s+rid\s+of|credit\s+"
    r"back)\s+(?:the\s+|my\s+|this\s+|that\s+|these\s+|those\s+|a\s+|an\s+|all\s+)?(?:\$?\d+(?:\.\d"
    r"{1,2})?\s+)?(?:late\s+|failed[- ]payment\s+|reschedul\w*\s+|reactivation\s+)?(?:fees?|"
    r"charges?|penalt(?:y|ies))\b",
    # Limit increase / decline override.
    r"\b(?:raise|increase|bump\s+up|boost|extend|up)\s+(?:my|the)\s+(?:spending\s+|credit\s+|"
    r"order\s+)?limit",
    r"\b(?:override|reverse|overturn|approve|push\s+through|un-?decline)\s+(?:the|my|this|that)\s+"
    r"(?:declined\s+)?(?:order|purchase|transaction|decline)",
    # Credit report correction.
    r"\b(?:correct|fix|remove|delete|dispute|update|change|erase)\b[^.?!\n]{0,50}\bcredit\s+"
    r"(?:report|history|file|record)",
    # Dispute handling.
    r"\b(?:file|open|start|submit|raise|lodge|escalate|update|close|cancel|withdraw)\s+(?:a|an|"
    r"the|my|this|that)\s+(?:\w+\s+)?(?:dispute|claim)\b",
    # Pausing payments.
    r"\b(?:pause|freeze|suspend|stop|hold|defer|skip|halt)\s+(?:all\s+)?(?:my\s+|the\s+|these\s+|"
    r"this\s+|those\s+|our\s+)?(?:upcoming\s+|next\s+|remaining\s+|future\s+)?(?:payments?|"
    r"installments?|billing|autopay|charges)\b",
    r"\b(?:stop|quit)\s+(?:charging|billing|debiting)\s+(?:me|us|my)\b",
)

_REQUEST_MARKERS = (
    r"\b(?:can|could|would|will)\s+(?:you|u|someone|somebody|sezzle|your\s+team)\b",
    r"\bplease\b",
    r"\bkindly\b",
    r"\b(?:i|we)\s*(?:'d|would)\s+like\b",
    r"\b(?:i|we)\s+(?:want|need|demand|expect|insist|am\s+asking|'m\s+asking|require)\b",
    r"\b(?:you|sezzle)\s+(?:need\s+to|have\s+to|must|should|better|ought\s+to)\b",
    r"\bi'm\s+requesting\b|\bi\s+request\b",
    # Imperative: the sentence starts with an action verb.
    r"^(?:(?:ok(?:ay)?|so|now|just|and|hi|hello|hey)[,\s]+)*(?:waive|remove|drop|cancel|refund|"
    r"reverse|forgive|file|open|start|submit|lodge|close|withdraw|pause|freeze|suspend|stop|hold|"
    r"defer|skip|halt|correct|fix|delete|erase|raise|increase|bump|boost|extend|override|"
    r"overturn|approve|get\s+rid|take)\b",
)

# A request sentence that is really asking for information ("can you explain how to ...").
_INFO_CUE_RE = re.compile(
    r"\b(?:how\s+(?:to|do|does|can|would|long|much)|whether|explain|what\s+happens|is\s+it\s+"
    r"possible|possible\s+to|if\s+(?:i|we)\s+can|allowed\s+to|able\s+to|can\s+i|could\s+i)\b"
)
# Sentences opening like a yes/no or wh-question about the process, not a request.
_QUESTION_OPENER_RE = re.compile(
    r"^(?:do|does|did|is|are|how|what|when|where|why|will\s+i|would\s+i|should\s+i)\b"
)

_HUMAN_REQUESTED = (
    rf"\b(?:connect|transfer|escalate|put|pass|hand|forward|send)\s+(?:me|this|it|my\s+(?:case|"
    rf"issue|request|ticket|complaint))\s+(?:through\s+|over\s+)?(?:to|with)\s+(?:a|an|the|your|"
    rf"some)?\s*{_AGENT}",
    rf"\b(?:i\s+(?:want|need|would\s+like|'d\s+like|wanna|demand|insist\s+on)|let\s+me|can\s+i|"
    rf"could\s+i|may\s+i)\s+(?:to\s+)?(?:talk|speak|chat)\s+(?:to|with)\s+(?:a|an|the|some|"
    rf"your)?\s*{_AGENT}",
    r"\b(?:i\s+(?:want|need|would\s+like|'d\s+like|demand)|give\s+me|get\s+me)\s+(?:a|an)\s+"
    r"(?:real\s+|live\s+|actual\s+)?(?:human|person|representative|live\s+agent|human\s+agent)\b",
    r"\bplease\s+escalate\b",
    r"\bescalate\s+(?:this|my\s+(?:case|issue|request|ticket|complaint))\b",
)


def _compile(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


_FRAUD_RE = _compile(_FRAUD)
_HARDSHIP_RE = _compile(_HARDSHIP)
_HUMAN_ONLY_DIRECT_RE = _compile(_HUMAN_ONLY_DIRECT)
_HUMAN_ONLY_ACTIONS_RE = _compile(_HUMAN_ONLY_ACTIONS)
_REQUEST_RE = _compile(_REQUEST_MARKERS)
_HUMAN_REQUESTED_RE = _compile(_HUMAN_REQUESTED)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?;\n]+")


@dataclass(frozen=True)
class TripwireResult:
    """Only a signal: which categories fired and the resulting ``forced_reason``. No text."""

    forced_reason: TripwireCategory | None
    fraud_mode: bool
    categories: tuple[TripwireCategory, ...]
    matched_rules: tuple[str, ...]

    @property
    def fired(self) -> bool:
        return self.forced_reason is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "forced_reason": self.forced_reason,
            "fraud_mode": self.fraud_mode,
            "categories": list(self.categories),
            "matched_rules": list(self.matched_rules),
        }


class Tripwire:
    """Conservative phrase classifier (security §3). Misses are the model's job; eval measures
    them as UNDER_ESCALATION."""

    def check(self, text: str) -> TripwireResult:
        norm = _normalise_text(text)
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(norm) if s.strip()]
        hits: dict[TripwireCategory, list[str]] = {}

        def record(category: TripwireCategory, rule: str) -> None:
            hits.setdefault(category, []).append(rule)

        for idx, pattern in enumerate(_FRAUD_RE):
            if pattern.search(norm):
                record("fraud", f"fraud[{idx}]")
        for idx, pattern in enumerate(_HARDSHIP_RE):
            if pattern.search(norm):
                record("hardship", f"hardship[{idx}]")
        for idx, pattern in enumerate(_HUMAN_ONLY_DIRECT_RE):
            if pattern.search(norm):
                record("human_only_action", f"human_only_action.direct[{idx}]")
        for sentence in sentences:
            if not any(m.search(sentence) for m in _REQUEST_RE) or _INFO_CUE_RE.search(sentence):
                continue
            for idx, pattern in enumerate(_HUMAN_ONLY_ACTIONS_RE):
                if pattern.search(sentence):
                    record("human_only_action", f"human_only_action.request[{idx}]")
        for sentence in sentences:
            if _QUESTION_OPENER_RE.search(sentence):
                continue
            for idx, pattern in enumerate(_HUMAN_REQUESTED_RE):
                if pattern.search(sentence):
                    record("human_requested", f"human_requested[{idx}]")

        categories = tuple(c for c in TRIPWIRE_PRECEDENCE if c in hits)
        rules = tuple(dict.fromkeys(r for c in categories for r in hits[c]))
        return TripwireResult(
            forced_reason=categories[0] if categories else None,
            fraud_mode="fraud" in hits,
            categories=categories,
            matched_rules=rules,
        )


def _normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = text.casefold()
    return re.sub(r"[ \t]+", " ", text)


# --- Output validator (SEC-06, security §4) -------------------------------------------------

Verdict = Literal["pass", "warn", "fail"]
CHECKS: tuple[str, ...] = (
    "schema",
    "citation",
    "order_id",
    "amount_ungrounded",
    "date_ungrounded",
    "action_claim",
    "commitment",
    "limit_disclosure",
    "escalation_coherence",
)


@dataclass(frozen=True)
class CheckVerdict:
    check: str
    verdict: Verdict
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"check": self.check, "verdict": self.verdict, "detail": self.detail}


@dataclass(frozen=True)
class ValidationContext:
    """What the validator needs to know about this case.

    ``caller_orders`` are the caller's orders from the repository (for ID ownership and fraud
    read-back); ``tool_result`` is the executed tool payload, or ``None`` if no tool ran."""

    shopper_message: str
    today: date
    caller_orders: tuple[Order, ...] = ()
    tool_result: Mapping[str, Any] | None = None
    fraud_mode: bool = False
    forced_reason: str | None = None

    @classmethod
    def for_case(
        cls,
        repo: OrdersRepository,
        user_id: str,
        shopper_message: str,
        *,
        tool_result: Mapping[str, Any] | None = None,
        fraud_mode: bool = False,
        forced_reason: str | None = None,
    ) -> ValidationContext:
        return cls(
            shopper_message=shopper_message,
            today=repo.today,
            caller_orders=repo.orders_for(user_id),
            tool_result=tool_result,
            fraud_mode=fraud_mode,
            forced_reason=forced_reason,
        )


@dataclass(frozen=True)
class ValidationResult:
    """All verdicts plus the answer with unknown citations dropped (``None`` if schema failed)."""

    verdicts: tuple[CheckVerdict, ...]
    answer: FinalAnswer | None = field(default=None)

    @property
    def ok(self) -> bool:
        return self.answer is not None and not self.failures

    @property
    def failures(self) -> tuple[CheckVerdict, ...]:
        return tuple(v for v in self.verdicts if v.verdict == "fail")

    @property
    def warnings(self) -> tuple[CheckVerdict, ...]:
        return tuple(v for v in self.verdicts if v.verdict == "warn")

    def verdict_of(self, check: str) -> Verdict | None:
        return next((v.verdict for v in self.verdicts if v.check == check), None)

    def failure_summary(self) -> str:
        """Short machine-generated list of violations for the repair call."""
        return "\n".join(f"- {v.check}: {v.detail}" for v in self.failures)

    def to_trace(self) -> list[dict[str, str]]:
        return [v.to_dict() for v in self.verdicts]


# Currency: "$12.34", "$1,234", "12.34 USD", "12 dollars".
_AMOUNT_RE = re.compile(
    r"\$\s?(?P<a>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?![\d.]*\d)"
    r"|\b(?P<b>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s?(?:usd|dollars?)\b",
    re.IGNORECASE,
)
_ORDER_ID_RE = re.compile(r"\bord_\d+\b", re.IGNORECASE)
_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_NAMED_DATE_RE = re.compile(
    rf"\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", re.IGNORECASE
)
_DAY_MONTH_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_ALT})\b\.?(?:,?\s+(\d{{4}}))?",
    re.IGNORECASE,
)
_SLASH_DATE_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])")

_ACTION_VERBS = (
    r"(?:rescheduled|moved|waived|refunded|paused|cancell?ed|filed|opened|removed|increased|"
    r"reactivated|credited)"
)
_FIRST_PERSON_ACTION_RE = re.compile(
    r"\b(?:i|we)(?:'ve|\s+have)?(?:\s+(?:already|just|now|successfully|also))?\s+"
    + _ACTION_VERBS
    + r"\b",
    re.IGNORECASE,
)
_AGENTLESS_ACTION_RE = re.compile(
    r"\byour\s+(?:[\w$.]+\s+){0,3}?(?P<subject>payments?|installments?|fees?|disputes?|due\s+"
    r"dates?|charges?|orders?|limits?)\s+(?:is\s+now|are\s+now|has\s+(?:now\s+)?been|have\s+(?:now"
    r"\s+)?been|was|were)\s+(?:successfully\s+|now\s+)?(?P<verb>rescheduled|moved|waived|refunded|"
    r"removed|filed|opened|paused|cancell?ed|credited)\b",
    re.IGNORECASE,
)
_COMMITMENT_RE = re.compile(
    r"\b(?:i|we)\s*(?:will|can|'ll|shall|am\s+going\s+to|'m\s+going\s+to|are\s+going\s+to|'re\s+"
    r"going\s+to)\s+(?!not\b|never\b)(?:(?:also|gladly|happily|definitely|certainly|immediately|"
    r"now|go\s+ahead\s+and|just)\s+)?(?:waive|remove\s+(?:the|your|this|that)\s+(?:[\w$.-]+\s+)?"
    r"(?:fees?|charges?)|refund\s+(?:you|your)|(?:increase|raise)\s+your\s+(?:\w+\s+)?limit|"
    r"approve|reschedule\s+(?:it|this|that|your\s+\w+)\s+for\s+you|pause)\b",
    re.IGNORECASE,
)
_LIMIT_DISCLOSURE_RES = (
    re.compile(
        r"\byour\s+(?:(?:exact|current|spending|actual|approved|credit|order|precise|total|max"
        r"imum)\s+){0,2}(?:limit|spending\s+power)\s+(?:is|was|will\s+be|would\s+be|of|sits\s+at|"
        r"stands\s+at)\s+(?:(?:currently|about|around|approximately|roughly|only|now|set\s+at|up\s+"
        r"to)\s+)*\$?\s?\d",
        re.IGNORECASE,
    ),
    re.compile(
        r"\$\s?\d[\d,]*(?:\.\d{1,2})?\s+(?:spending\s+|credit\s+|order\s+|approved\s+)?(?:limit|"
        r"spending\s+power)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:limit|spending\s+power)\s+(?:is\s+|of\s+|at\s+|to\s+|currently\s+)+\$\s?\d",
        re.IGNORECASE,
    ),
)
_HANDOFF_RE = re.compile(r"\b(?:human|specialist|agent|team|escalat\w*)", re.IGNORECASE)
_MONEY_KEYS = frozenset({"amount", "total", "unpaid_balance"})


class OutputValidator:
    """Narrow invariants on the model's typed claims; it never generates answer text."""

    def __init__(self, corpus: PolicyCorpus) -> None:
        self.policy_ids = frozenset(corpus.ids)
        self.corpus_amounts = frozenset(
            cents for p in corpus for cents in _amounts_in(f"{p.title}\n{p.text}")
        )

    def validate(
        self, raw: FinalAnswer | Mapping[str, Any] | None, ctx: ValidationContext
    ) -> ValidationResult:
        final, schema = self._check_schema(raw)
        if final is None:
            return ValidationResult(verdicts=(schema,), answer=None)
        final, citation = self._check_citation(final)
        text = final.answer
        verdicts = (
            schema,
            citation,
            self._check_order_ids(text, ctx),
            self._check_amounts(text, ctx),
            self._check_dates(text, ctx),
            self._check_action_claims(text, ctx),
            _check_commitment(text),
            _check_limit_disclosure(text),
            _check_escalation_coherence(final, ctx),
        )
        return ValidationResult(verdicts=verdicts, answer=final)

    # schema ------------------------------------------------------------------------------
    @staticmethod
    def _check_schema(
        raw: FinalAnswer | Mapping[str, Any] | None,
    ) -> tuple[FinalAnswer | None, CheckVerdict]:
        if raw is None:
            return None, CheckVerdict("schema", "fail", "no JSON answer was returned")
        try:
            final = raw if isinstance(raw, FinalAnswer) else FinalAnswer.model_validate(dict(raw))
        except (ValidationError, TypeError, ValueError) as err:
            return None, CheckVerdict("schema", "fail", _schema_errors(err))
        if not final.answer.strip():
            return None, CheckVerdict("schema", "fail", "answer is empty")
        return final, CheckVerdict("schema", "pass")

    # citation ----------------------------------------------------------------------------
    def _check_citation(self, final: FinalAnswer) -> tuple[FinalAnswer, CheckVerdict]:
        kept = list(dict.fromkeys(c for c in final.cited_policies if c in self.policy_ids))
        dropped = [c for c in final.cited_policies if c not in self.policy_ids]
        notes = []
        if dropped:
            notes.append(f"dropped unknown policy IDs {dropped}")
        if final.policy_applied and not kept:
            notes.append("policy_applied is true but no valid policy is cited")
        cleaned = (
            final
            if kept == final.cited_policies
            else final.model_copy(update={"cited_policies": kept})
        )
        verdict: Verdict = "warn" if notes else "pass"
        return cleaned, CheckVerdict("citation", verdict, "; ".join(notes))

    # order_id ----------------------------------------------------------------------------
    @staticmethod
    def _check_order_ids(text: str, ctx: ValidationContext) -> CheckVerdict:
        ids = list(dict.fromkeys(m.group(0).lower() for m in _ORDER_ID_RE.finditer(text)))
        merchants = _fraud_merchants(text, ctx) if ctx.fraud_mode else []
        if ctx.fraud_mode and (ids or merchants):
            shown = ids + merchants
            return CheckVerdict("order_id", "fail", f"fraud mode: order details read back {shown}")
        if not ids:
            return CheckVerdict("order_id", "pass")
        own = {o.order_id for o in ctx.caller_orders}
        typed = ctx.shopper_message.casefold()
        tool_not_found = ctx.tool_result is not None and ctx.tool_result.get("status") == (
            "not_found"
        )
        foreign = [i for i in ids if i not in own]
        echoed = [i for i in foreign if i in typed and tool_not_found]
        bad = [i for i in foreign if i not in echoed]
        if bad:
            return CheckVerdict("order_id", "fail", f"order IDs not on the caller's account {bad}")
        if echoed:
            return CheckVerdict("order_id", "warn", f"echoed shopper-typed not-found IDs {echoed}")
        return CheckVerdict("order_id", "pass")

    # amount_ungrounded -------------------------------------------------------------------
    def _check_amounts(self, text: str, ctx: ValidationContext) -> CheckVerdict:
        amounts = list(dict.fromkeys(_amounts_in(text)))
        if not amounts:
            return CheckVerdict("amount_ungrounded", "pass")
        if ctx.fraud_mode:
            caller = {c for o in ctx.caller_orders for c in _money_in(o.model_dump(mode="json"))}
            leaked = [a for a in amounts if a in caller]
            if leaked:
                return CheckVerdict(
                    "amount_ungrounded",
                    "fail",
                    f"fraud mode: caller order amounts read back {_fmt_cents(leaked)}",
                )
        grounded = self.corpus_amounts | frozenset(_money_in(ctx.tool_result or {}))
        ungrounded = [a for a in amounts if a not in grounded]
        if ungrounded:
            return CheckVerdict(
                "amount_ungrounded",
                "fail",
                f"amounts in neither the tool result nor the policies {_fmt_cents(ungrounded)}",
            )
        return CheckVerdict("amount_ungrounded", "pass")

    # date_ungrounded ---------------------------------------------------------------------
    @staticmethod
    def _check_dates(text: str, ctx: ValidationContext) -> CheckVerdict:
        dates = list(dict.fromkeys(_dates_in(text, ctx.today.year)))
        if not dates:
            return CheckVerdict("date_ungrounded", "pass")
        grounded = {ctx.today} | set(_dates_in_data(ctx.tool_result or {}))
        ungrounded = [d.isoformat() for d in dates if d not in grounded]
        if ungrounded:
            return CheckVerdict(
                "date_ungrounded", "warn", f"dates not in the tool result or today {ungrounded}"
            )
        return CheckVerdict("date_ungrounded", "pass")

    # action_claim ------------------------------------------------------------------------
    @staticmethod
    def _check_action_claims(text: str, ctx: ValidationContext) -> CheckVerdict:
        claims = [m.group(0) for m in _FIRST_PERSON_ACTION_RE.finditer(text)]
        recorded = _recorded_states(ctx.tool_result or {})
        for match in _AGENTLESS_ACTION_RE.finditer(text):
            verb = match.group("verb").lower()
            if verb not in recorded:
                claims.append(match.group(0))
        if claims:
            return CheckVerdict("action_claim", "fail", f"claims a performed action {claims}")
        return CheckVerdict("action_claim", "pass")


def _check_commitment(text: str) -> CheckVerdict:
    promises = [m.group(0) for m in _COMMITMENT_RE.finditer(text)]
    if promises:
        return CheckVerdict("commitment", "fail", f"promises a human-only outcome {promises}")
    return CheckVerdict("commitment", "pass")


def _check_limit_disclosure(text: str) -> CheckVerdict:
    hits = [m.group(0) for pattern in _LIMIT_DISCLOSURE_RES for m in pattern.finditer(text)]
    if hits:
        return CheckVerdict("limit_disclosure", "fail", f"states a limit amount {hits}")
    return CheckVerdict("limit_disclosure", "pass")


def _check_escalation_coherence(final: FinalAnswer, ctx: ValidationContext) -> CheckVerdict:
    escalating = bool(ctx.forced_reason) or final.escalation_reason != "none"
    if escalating and not _HANDOFF_RE.search(final.answer):
        return CheckVerdict(
            "escalation_coherence", "fail", "escalating but the answer states no hand-off"
        )
    return CheckVerdict("escalation_coherence", "pass")


# --- helpers --------------------------------------------------------------------------------


def _schema_errors(err: Exception) -> str:
    if isinstance(err, ValidationError):
        parts = [f"{'.'.join(map(str, e['loc'])) or 'answer'}: {e['msg']}" for e in err.errors()]
        return "; ".join(parts[:5])
    return str(err)[:200]


def _to_cents(value: str) -> int | None:
    try:
        return int((Decimal(value.replace(",", "")) * 100).to_integral_value())
    except InvalidOperation:
        return None


def _amounts_in(text: str) -> Iterator[int]:
    for match in _AMOUNT_RE.finditer(text):
        cents = _to_cents(match.group("a") or match.group("b"))
        if cents is not None:
            yield cents


def _money_in(data: Any) -> Iterator[int]:
    """Cents of every money field (``amount``, ``total``, ``unpaid_balance``) in JSON data."""
    if isinstance(data, Mapping):
        for key, value in data.items():
            is_number = isinstance(value, int | float) and not isinstance(value, bool)
            if key in _MONEY_KEYS and is_number:
                cents = _to_cents(str(value))
                if cents is not None:
                    yield cents
            else:
                yield from _money_in(value)
    elif isinstance(data, Sequence) and not isinstance(data, str | bytes):
        for item in data:
            yield from _money_in(item)


def _fmt_cents(values: Iterable[int]) -> list[str]:
    return [f"${v / 100:.2f}" for v in values]


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _dates_in(text: str, default_year: int) -> Iterator[date]:
    for m in _ISO_DATE_RE.finditer(text):
        found = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if found:
            yield found
    for m in _NAMED_DATE_RE.finditer(text):
        year = int(m.group(3)) if m.group(3) else default_year
        found = _safe_date(year, _MONTHS[m.group(1).lower()], int(m.group(2)))
        if found:
            yield found
    for m in _DAY_MONTH_RE.finditer(text):
        year = int(m.group(3)) if m.group(3) else default_year
        found = _safe_date(year, _MONTHS[m.group(2).lower()], int(m.group(1)))
        if found:
            yield found
    for m in _SLASH_DATE_RE.finditer(text):
        year = default_year
        if m.group(3):
            year = int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0)
        found = _safe_date(year, int(m.group(1)), int(m.group(2)))
        if found:
            yield found


def _dates_in_data(data: Any) -> Iterator[date]:
    if isinstance(data, Mapping):
        for value in data.values():
            yield from _dates_in_data(value)
    elif isinstance(data, str):
        match = _ISO_DATE_RE.fullmatch(data)
        if match:
            found = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if found:
                yield found
    elif isinstance(data, Sequence) and not isinstance(data, bytes):
        for item in data:
            yield from _dates_in_data(item)


def _recorded_states(tool_result: Mapping[str, Any]) -> frozenset[str]:
    """Action verbs that describe state already recorded in this case's tool data."""
    states: set[str] = set()
    for order in tool_result.get("orders") or ():
        if not isinstance(order, Mapping):
            continue
        installments = order.get("installments") or ()
        statuses = {i.get("status") for i in installments if isinstance(i, Mapping)}
        if "paused" in statuses:
            states.add("paused")
        if order.get("refund"):
            states.add("refunded")
        if isinstance(order.get("reschedules_used"), int) and order["reschedules_used"] > 0:
            states.update({"rescheduled", "moved"})
    return frozenset(states)


def _fraud_merchants(text: str, ctx: ValidationContext) -> list[str]:
    """Caller merchant names in the answer that the shopper did not type themselves."""
    answer = text.casefold()
    typed = ctx.shopper_message.casefold()
    names = dict.fromkeys(o.merchant for o in ctx.caller_orders)
    return [n for n in names if n.casefold() in answer and n.casefold() not in typed]
