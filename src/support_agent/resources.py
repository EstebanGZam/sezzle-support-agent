"""Load and validate the static resources once (architecture §1, §2).

Everything here is immutable and shared read-only across cases: the policy corpus
(``POL-01..12``), the orders repository (strict Pydantic models) and ``today``, which comes
from ``data/orders.json`` and never from the system clock (SEZ-F06).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from support_agent.config import Settings

ORDER_ID_PATTERN = r"^ord_\d{1,6}$"
USER_ID_PATTERN = r"^u\d{1,6}$"
POLICY_FILE_RE = re.compile(r"^(\d{2})-[a-z0-9-]+\.md$")

InstallmentStatus = Literal["paid", "upcoming", "failed", "paused"]


class _Record(BaseModel):
    """Strict, immutable record; unknown fields are rejected."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class User(_Record):
    user_id: str = Field(pattern=USER_ID_PATTERN)
    name: str
    account_status: str
    # Vestigial in the data; order-level ``reschedules_used`` is authoritative (A-05).
    reschedules_used: Mapping[str, int]

    @field_validator("reschedules_used")
    @classmethod
    def _freeze(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        return MappingProxyType(dict(value))

    @field_serializer("reschedules_used")
    def _dump_mapping(self, value: Mapping[str, int]) -> dict[str, int]:
        return dict(value)


class Installment(_Record):
    installment: int = Field(ge=1)
    amount: float = Field(ge=0)
    due_date: date
    status: InstallmentStatus
    paid_date: date | None


class Refund(_Record):
    amount: float = Field(ge=0)
    issued_date: date
    status: str


class Order(_Record):
    order_id: str = Field(pattern=ORDER_ID_PATTERN)
    user_id: str = Field(pattern=USER_ID_PATTERN)
    merchant: str
    order_date: date
    total: float = Field(ge=0)
    plan: str
    status: str
    reschedules_used: int = Field(ge=0)
    refund: Refund | None
    installments: tuple[Installment, ...]


class OrdersFile(_Record):
    """Schema of ``data/orders.json``."""

    generated_seed: int
    today: date
    users: tuple[User, ...]
    orders: tuple[Order, ...]


@dataclass(frozen=True)
class OrdersRepository:
    """Read-only access to users and orders; lookups are always scoped to one user."""

    today: date
    users: tuple[User, ...]
    orders: tuple[Order, ...]
    _by_user: Mapping[str, tuple[Order, ...]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        user_ids = [u.user_id for u in self.users]
        if len(set(user_ids)) != len(user_ids):
            raise ValueError("duplicate user_id in orders data")
        order_ids = [o.order_id for o in self.orders]
        if len(set(order_ids)) != len(order_ids):
            raise ValueError("duplicate order_id in orders data")
        by_user: dict[str, list[Order]] = {uid: [] for uid in user_ids}
        for order in self.orders:
            if order.user_id not in by_user:
                raise ValueError(f"order {order.order_id} references unknown user {order.user_id}")
            by_user[order.user_id].append(order)
        frozen = MappingProxyType({uid: tuple(orders) for uid, orders in by_user.items()})
        object.__setattr__(self, "_by_user", frozen)

    @classmethod
    def from_file(cls, path: Path) -> OrdersRepository:
        data = OrdersFile.model_validate_json(path.read_bytes())
        return cls(today=data.today, users=data.users, orders=data.orders)

    def has_user(self, user_id: str) -> bool:
        return user_id in self._by_user

    def orders_for(self, user_id: str) -> tuple[Order, ...]:
        """The caller's orders only; an unknown user has none."""
        return self._by_user.get(user_id, ())


class Policy(_Record):
    id: str = Field(pattern=r"^POL-\d{2}$")
    title: str = Field(min_length=1)
    text: str
    filename: str


@dataclass(frozen=True)
class PolicyCorpus:
    """Policies in stable ``POL-NN`` order; ``corpus_hash`` covers the raw file bytes."""

    policies: tuple[Policy, ...]
    corpus_hash: str

    @classmethod
    def from_dir(cls, directory: Path) -> PolicyCorpus:
        numbered: dict[int, Path] = {}
        for path in directory.iterdir():
            match = POLICY_FILE_RE.match(path.name)
            if not match:
                continue
            number = int(match.group(1))
            if number in numbered:
                raise ValueError(f"duplicate policy number {number:02d} in {directory}")
            numbered[number] = path
        if not numbered:
            raise ValueError(f"no policy files found in {directory}")

        digest = hashlib.sha256()
        policies = []
        for number in sorted(numbered):
            path = numbered[number]
            raw = path.read_bytes()
            digest.update(raw)
            title, text = _split_heading(raw.decode("utf-8"), path.name)
            policies.append(
                Policy(id=f"POL-{number:02d}", title=title, text=text, filename=path.name)
            )
        return cls(policies=tuple(policies), corpus_hash=digest.hexdigest())

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(p.id for p in self.policies)

    def get(self, policy_id: str) -> Policy | None:
        return next((p for p in self.policies if p.id == policy_id), None)

    def __iter__(self) -> Iterator[Policy]:
        return iter(self.policies)

    def __len__(self) -> int:
        return len(self.policies)


def _split_heading(content: str, filename: str) -> tuple[str, str]:
    """Title from the first ``# `` heading; text is the body that follows it."""
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title, "\n".join(lines[index + 1 :]).strip()
            break
    raise ValueError(f"policy {filename} has no '# ' title heading")


@dataclass(frozen=True)
class Resources:
    """Everything loaded once per batch and shared (immutable) across cases."""

    settings: Settings
    policies: PolicyCorpus
    orders: OrdersRepository

    @property
    def today(self) -> date:
        return self.orders.today

    @classmethod
    def load(cls, settings: Settings) -> Resources:
        return cls(
            settings=settings,
            policies=PolicyCorpus.from_dir(settings.policies_dir),
            orders=OrdersRepository.from_file(settings.orders_path),
        )
