import dataclasses
import hashlib
import json
import shutil
from datetime import date

import pytest
from pydantic import ValidationError

from support_agent.config import Settings
from support_agent.resources import (
    OrdersRepository,
    PolicyCorpus,
    Resources,
)


@pytest.fixture(scope="module")
def settings():
    return Settings.from_env({"LLM_PROVIDER": "fake"})


@pytest.fixture(scope="module")
def resources(settings):
    return Resources.load(settings)


def raw_orders(settings):
    return json.loads(settings.orders_path.read_text())


def write_orders(tmp_path, data):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps(data))
    return path


def test_counts_and_today(resources):
    assert len(resources.policies) == 12
    assert len(resources.orders.orders) == 23
    assert len(resources.orders.users) == 8
    assert resources.today == date(2026, 7, 1)
    assert resources.orders.today == date(2026, 7, 1)


def test_policy_ids_titles_and_order(resources, settings):
    corpus = resources.policies
    assert corpus.ids == tuple(f"POL-{n:02d}" for n in range(1, 13))
    for policy in corpus:
        number = int(policy.id.removeprefix("POL-"))
        assert policy.filename.startswith(f"{number:02d}-")
        heading = (settings.policies_dir / policy.filename).read_text().splitlines()[0]
        assert heading == f"# {policy.title}"
        assert policy.text
        assert not policy.text.startswith("# ")
    assert corpus.get("POL-01").title == "Payment Schedules (Pay-in-4)"
    assert corpus.get("POL-99") is None


def test_corpus_hash_is_sha256_of_files_in_pol_order(resources, settings):
    digest = hashlib.sha256()
    for policy in resources.policies:
        digest.update((settings.policies_dir / policy.filename).read_bytes())
    assert resources.policies.corpus_hash == digest.hexdigest()


def test_policy_order_is_numeric_not_filesystem(tmp_path, settings):
    for name in ("10-b.md", "02-a.md", "01-c.md"):
        (tmp_path / name).write_text(f"# Title {name}\nBody\n")
    (tmp_path / "README.md").write_text("ignored")
    corpus = PolicyCorpus.from_dir(tmp_path)
    assert corpus.ids == ("POL-01", "POL-02", "POL-10")


def test_policy_without_heading_is_rejected(tmp_path):
    (tmp_path / "01-x.md").write_text("no heading here\n")
    with pytest.raises(ValueError, match="heading"):
        PolicyCorpus.from_dir(tmp_path)


def test_empty_policy_dir_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="no policy files"):
        PolicyCorpus.from_dir(tmp_path)


def test_orders_for_is_scoped_to_the_user(resources):
    repo = resources.orders
    for user in repo.users:
        orders = repo.orders_for(user.user_id)
        assert orders
        assert all(o.user_id == user.user_id for o in orders)
    assert sum(len(repo.orders_for(u.user_id)) for u in repo.users) == 23
    assert repo.orders_for("u999") == ()
    assert repo.has_user("u001")
    assert not repo.has_user("u999")


def test_models_are_immutable(resources):
    repo = resources.orders
    order = repo.orders[0]
    with pytest.raises(ValidationError):
        order.total = 1.0
    with pytest.raises(ValidationError):
        order.installments[0].amount = 1.0
    with pytest.raises(TypeError):
        order.installments[0] = order.installments[1]  # tuple
    with pytest.raises(TypeError):
        repo.users[0].reschedules_used["x"] = 1  # read-only mapping
    with pytest.raises(TypeError):
        repo._by_user["u999"] = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        repo.today = date(2030, 1, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        resources.policies = None
    with pytest.raises(ValidationError):
        resources.policies.policies[0].text = "changed"


def test_repository_orders_for_returns_tuples(resources):
    assert isinstance(resources.orders.orders_for("u001"), tuple)


def test_user_model_dumps_to_json(resources):
    assert resources.orders.users[0].model_dump(mode="json")["reschedules_used"] == {}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["orders"][0].__setitem__("total", "147.75"),  # string, strict
        lambda d: d["orders"][0].__setitem__("unexpected", 1),  # extra field
        lambda d: d["orders"][0]["installments"][0].__setitem__("status", "late"),
        lambda d: d["orders"][0]["installments"][0].__setitem__("due_date", "07/11/2026"),
        lambda d: d["orders"][0].__setitem__("order_id", "order-1"),
        lambda d: d.__setitem__("today", "yesterday"),
        lambda d: d["orders"][0].pop("merchant"),
        lambda d: d["users"][0].__setitem__("reschedules_used", {"ord_3001": "1"}),
    ],
)
def test_bad_data_raises_validation_error(tmp_path, settings, mutate):
    data = raw_orders(settings)
    mutate(data)
    with pytest.raises(ValidationError):
        OrdersRepository.from_file(write_orders(tmp_path, data))


def test_duplicate_order_id_rejected(tmp_path, settings):
    data = raw_orders(settings)
    data["orders"][1]["order_id"] = data["orders"][0]["order_id"]
    with pytest.raises(ValueError, match="duplicate order_id"):
        OrdersRepository.from_file(write_orders(tmp_path, data))


def test_order_for_unknown_user_rejected(tmp_path, settings):
    data = raw_orders(settings)
    data["orders"][0]["user_id"] = "u999"
    with pytest.raises(ValueError, match="unknown user"):
        OrdersRepository.from_file(write_orders(tmp_path, data))


def test_today_comes_from_the_data_file(tmp_path, settings):
    data = raw_orders(settings)
    data["today"] = "2030-01-15"
    shutil.copytree(settings.policies_dir, tmp_path / "policies")
    write_orders(tmp_path, data)
    loaded = Resources.load(dataclasses.replace(settings, data_dir=tmp_path))
    assert loaded.today == date(2030, 1, 15)
