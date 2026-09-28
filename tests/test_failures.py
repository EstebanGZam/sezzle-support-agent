"""Provider-failure behaviour (evaluation §7, architecture §7, OWN-15, SEC-10) — fake LLM only.

Every scenario must write a valid line per id, record the error class in the trace, and stay
within 3 semantic calls per case and ``LLM_MAX_ATTEMPTS`` attempts per semantic call.
"""

import importlib.util
import io
import json
import sys

import pytest

from support_agent.agent import AgentStatics, CallBudget, Case, answer_case
from support_agent.config import PROJECT_ROOT, Settings
from support_agent.guards import SAFE_FAILURE_ANSWER
from support_agent.llm import FakeLLM
from support_agent.resources import Resources

MAX_ATTEMPTS = 2


@pytest.fixture(scope="module")
def resources():
    return Resources.load(Settings.from_env({"LLM_PROVIDER": "fake"}))


@pytest.fixture(scope="module")
def statics(resources):
    return AgentStatics.build(resources)


@pytest.fixture(scope="module")
def cli():
    spec = importlib.util.spec_from_file_location("run_cases_cli", PROJECT_ROOT / "run_cases.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


def _final(answer="Pay in 4 splits a purchase into four payments."):
    return {
        "final": {
            "answer": answer,
            "escalation_reason": "none",
            "policy_applied": False,
            "cited_policies": [],
        }
    }


def _err(kind):
    return {"error": kind}


def _answer(resources, statics, script, *, fallback=None, question="How does pay in 4 work?"):
    llm = FakeLLM(script, fallback_model=fallback, max_attempts=MAX_ATTEMPTS)
    case = Case(id="f1", user_id="u002", question=question)
    return answer_case(resources, llm, case, statics=statics), llm


def _assert_budgets(result):
    assert len(result.trace.llm_calls) <= 3
    for call in result.trace.llm_calls:
        assert len(call.attempts) <= MAX_ATTEMPTS


def _assert_safe_failure(result, error_class):
    assert result.answer == SAFE_FAILURE_ANSWER
    assert result.route == "escalate"
    assert result.error_class == error_class
    assert result.trace.safe_failure
    assert "ord_" not in result.answer


# --- per-class behaviour at the case level -------------------------------------------------


@pytest.mark.parametrize("kind", ["rate_limit_minute", "server_5xx", "timeout"])
def test_retryable_error_recovers_on_same_model(resources, statics, kind):
    result, llm = _answer(resources, statics, [_err(kind), _final()])
    assert result.error_class is None and result.route == "policy"
    assert llm.attempt_models == ["fake-primary", "fake-primary"]
    assert [a["status"] for a in result.trace.llm_calls[0].attempts] == ["retry", "ok"]
    _assert_budgets(result)


@pytest.mark.parametrize("kind", ["rate_limit_minute", "server_5xx", "timeout"])
def test_retryable_error_persisting_is_safe_failure(resources, statics, kind):
    result, _ = _answer(resources, statics, [_err(kind), _err(kind)])
    _assert_safe_failure(result, kind)
    assert result.trace.llm_calls[0].outcome == "error"
    _assert_budgets(result)


@pytest.mark.parametrize("kind", ["overloaded", "rate_limit_minute", "server_5xx", "timeout"])
def test_transient_error_tries_the_fallback_before_a_same_model_retry(resources, statics, kind):
    result, llm = _answer(resources, statics, [_err(kind), _final()], fallback="fake-fallback")
    assert result.error_class is None and result.route == "policy"
    assert llm.attempt_models == ["fake-primary", "fake-fallback"]
    assert result.trace.fallback_used is True
    _assert_budgets(result)


def test_overloaded_without_fallback_is_safe_failure_without_retry(resources, statics):
    result, llm = _answer(resources, statics, [_err("overloaded"), _final()])
    _assert_safe_failure(result, "overloaded")
    assert llm.attempt_models == ["fake-primary"]


def test_overloaded_on_both_models_records_fallback_use(resources, statics):
    script = [_err("overloaded"), _err("overloaded")]
    result, llm = _answer(resources, statics, script, fallback="fake-fallback")
    _assert_safe_failure(result, "overloaded")
    assert llm.attempt_models == ["fake-primary", "fake-fallback"]
    assert result.trace.fallback_used is True
    _assert_budgets(result)


@pytest.mark.parametrize("kind", ["quota_daily", "model_not_found"])
def test_fallback_eligible_error_uses_fallback(resources, statics, kind):
    result, llm = _answer(resources, statics, [_err(kind), _final()], fallback="fake-fallback")
    assert result.error_class is None
    assert llm.attempt_models == ["fake-primary", "fake-fallback"]
    assert result.trace.fallback_used is True
    assert result.trace.model == "fake-fallback"
    _assert_budgets(result)


@pytest.mark.parametrize("kind", ["quota_daily", "model_not_found"])
def test_fallback_eligible_error_without_fallback_is_safe_failure(resources, statics, kind):
    result, llm = _answer(resources, statics, [_err(kind)])
    _assert_safe_failure(result, kind)
    assert len(llm.attempt_models) == 1


def test_quota_daily_model_not_called_again_in_batch(resources, statics):
    llm = FakeLLM([_err("quota_daily"), _final(), _final()], fallback_model="fake-fallback")
    for case_id in ("q1", "q2"):
        case = Case(id=case_id, user_id="u002", question="How does pay in 4 work?")
        assert answer_case(resources, llm, case, statics=statics).error_class is None
    assert llm.attempt_models == ["fake-primary", "fake-fallback", "fake-fallback"]


@pytest.mark.parametrize("kind", ["bad_request", "blocked_safety"])
def test_non_retryable_error_is_safe_failure(resources, statics, kind):
    result, llm = _answer(resources, statics, [_err(kind)], fallback="fake-fallback")
    _assert_safe_failure(result, kind)
    assert len(llm.attempt_models) == 1


def test_error_on_post_tool_call_is_safe_failure_without_data(resources, statics):
    script = [{"function_call": {"name": "get_my_orders", "args": {}}}, _err("bad_request")]
    result, _ = _answer(resources, statics, script, question="When is my next payment?")
    _assert_safe_failure(result, "bad_request")
    assert result.trace.route_inputs["tool_executed"] is True
    assert "ord_" not in json.dumps(result.trace.to_dict()["route_inputs"])


def test_error_on_repair_call_is_safe_failure(resources, statics):
    script = [_final("I've waived your late fee."), _err("server_5xx"), _err("server_5xx")]
    result, _ = _answer(resources, statics, script)
    _assert_safe_failure(result, "server_5xx")
    assert result.trace.repair_attempted


@pytest.mark.parametrize(
    "bad_step",
    [
        {"function_call": {"name": "drop_tables", "args": {}}},
        {"function_call": {"name": "get_my_orders", "args": {"order_id": ["x"]}}},
        {"function_call": {"name": "get_my_orders", "args": {"user_id": "u001"}}},
        {"final": {"answer": "missing fields"}},
        {"text": "{not json"},
    ],
)
def test_malformed_output_repair_then_validation_exhausted(resources, statics, bad_step):
    result, llm = _answer(resources, statics, [bad_step, bad_step])
    _assert_safe_failure(result, "validation_exhausted")
    assert result.trace.repair_attempted
    assert result.trace.route_inputs["tool_executed"] is False
    assert all(r.tool_mode == "none" for r in llm.requests[1:])
    _assert_budgets(result)


def test_validation_exhausted_after_repair(resources, statics):
    script = [_final("Your limit is $500."), _final("Your limit is $500.")]
    result, _ = _answer(resources, statics, script)
    _assert_safe_failure(result, "validation_exhausted")


def test_auth_billing_at_case_level_is_safe_failure(resources, statics):
    result, llm = _answer(resources, statics, [_err("auth_billing")], fallback="fake-fallback")
    _assert_safe_failure(result, "auth_billing")
    assert len(llm.attempt_models) == 1


def test_batch_limit_for_remaining_cases(resources, statics):
    llm = FakeLLM(None)
    budget = CallBudget(2)
    results = [
        answer_case(
            resources,
            llm,
            Case(id=f"b{i}", user_id="u001", question="How does it work?"),
            statics=statics,
            budget=budget,
        )
        for i in range(4)
    ]
    assert [r.error_class for r in results] == [None, None, "batch_limit", "batch_limit"]
    assert len(llm.requests) == 2
    for r in results[2:]:
        _assert_safe_failure(r, "batch_limit")


# --- per-case deadline (architecture §7, R-01 #4) -------------------------------------------


class _Clock:
    """Fake monotonic clock shared by ``answer_case`` and the LLM's ``AttemptRunner``."""

    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _TimedFakeLLM(FakeLLM):
    """FakeLLM whose attempts take simulated time: step ``i`` lasts ``durations[i]`` seconds, cut
    off at the attempt's timeout (as a real client timeout would)."""

    def __init__(self, script, durations, clock, **kwargs):
        super().__init__(script, clock=clock, sleep=clock.advance, **kwargs)
        self.clock = clock
        self.durations = list(durations)
        self.attempt_timeouts = []

    def _attempt(self, model, timeout_s):
        self.attempt_timeouts.append(timeout_s)
        self.clock.advance(min(self.durations.pop(0), timeout_s))
        return super()._attempt(model, timeout_s)


def _timed(resources, statics, script, durations, *, budget=None, timeout_s=12.0):
    clock = _Clock()
    start = clock.now
    llm = _TimedFakeLLM(script, durations, clock, max_attempts=MAX_ATTEMPTS, timeout_s=timeout_s)
    case = Case(id="d1", user_id="u002", question="When is my next payment?")
    result = answer_case(resources, llm, case, statics=statics, budget=budget, clock=clock)
    return result, llm, start


def test_every_call_carries_the_same_absolute_case_deadline(resources, statics):
    script = [{"function_call": {"name": "get_my_orders", "args": {}}}, _final()]
    result, llm, start = _timed(resources, statics, script, [3.0, 3.0])
    assert result.error_class is None
    deadline = start + resources.settings.case_deadline_s
    assert [r.deadline for r in llm.requests] == [deadline, deadline]


def test_retry_attempt_timeout_is_capped_by_the_case_deadline(resources, statics):
    # Call 1 takes 10 s; call 2 times out after its full 12 s and is retried with the 8 s left.
    script = [
        {"function_call": {"name": "get_my_orders", "args": {}}},
        _err("timeout"),
        _err("timeout"),
    ]
    result, llm, start = _timed(resources, statics, script, [10.0, 60.0, 60.0])
    _assert_safe_failure(result, "timeout")
    assert llm.attempt_timeouts == [12.0, 12.0, pytest.approx(8.0)]
    assert llm.clock.now - start <= resources.settings.case_deadline_s
    _assert_budgets(result)


def test_exhausted_deadline_stops_the_same_model_retry(resources, statics):
    # Without a deadline this timeout is retried and recovers (see the retryable tests above).
    deadline_s = resources.settings.case_deadline_s
    result, llm, _ = _timed(
        resources, statics, [_err("timeout"), _final()], [deadline_s - 0.2], timeout_s=deadline_s
    )
    _assert_safe_failure(result, "timeout")
    assert llm.attempt_models == ["fake-primary"]
    assert [a["status"] for a in result.trace.llm_calls[0].attempts] == ["failed"]
    assert llm.remaining_steps == 1


def test_exhausted_deadline_stops_later_calls_without_spending_budget(resources, statics):
    # Call 1 answers invalidly just before the deadline: no repair call is made.
    deadline_s = resources.settings.case_deadline_s
    script = [_final("Your limit is $500."), _final()]
    budget = CallBudget(10)
    result, llm, _ = _timed(
        resources, statics, script, [deadline_s - 0.2], budget=budget, timeout_s=deadline_s
    )
    _assert_safe_failure(result, "timeout")
    assert result.trace.repair_attempted
    assert len(llm.requests) == 1 and len(result.trace.llm_calls) == 1
    assert llm.remaining_steps == 1
    assert budget.used == 1


# --- batch level through the CLI -----------------------------------------------------------


def _cases(tmp_path, n):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        "".join(
            json.dumps({"id": f"k{i}", "user_id": "u002", "question": "How does it work?"}) + "\n"
            for i in range(n)
        ),
        encoding="utf-8",
    )
    return path


def _script(tmp_path, steps, on_exhausted="error"):
    path = tmp_path / "script.json"
    path.write_text(json.dumps({"steps": steps, "on_exhausted": on_exhausted}), encoding="utf-8")
    return path


def _cli_run(cli, tmp_path, cases, env):
    answers = tmp_path / "answers.jsonl"
    err = io.StringIO()
    code = cli.main([str(cases), str(answers)], environ=env, stderr=err)
    rows = [json.loads(x) for x in answers.read_text(encoding="utf-8").splitlines()]
    traces = [
        json.loads(x)
        for x in (tmp_path / "answers.trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return code, rows, traces, err.getvalue()


def test_auth_billing_circuit_breaker_writes_all_lines_and_exits_3(cli, tmp_path):
    key = "AIzaFAKE-circuit-breaker-key-0000"
    script = _script(tmp_path, [_final(), _err("auth_billing")])
    env = {"LLM_PROVIDER": "fake", "FAKE_LLM_SCRIPT": str(script), "GOOGLE_API_KEY": key}
    code, rows, traces, err = _cli_run(cli, tmp_path, _cases(tmp_path, 4), env)
    assert code == 3
    assert [r["id"] for r in rows] == ["k0", "k1", "k2", "k3"]
    assert rows[0]["answer"] != SAFE_FAILURE_ANSWER
    for row, trace in zip(rows[1:], traces[1:], strict=True):
        assert row["answer"] == SAFE_FAILURE_ANSWER and row["route"] == "escalate"
        assert trace["error_class"] == "auth_billing"
    # No calls after the breaker opened: the breaker case made one call, the rest none.
    assert len(traces[1]["llm_calls"]) == 1
    assert all(t["llm_calls"] == [] for t in traces[2:])
    assert err.count("circuit breaker") == 1
    assert key not in err
    config = json.loads((tmp_path / "answers.config.json").read_text())
    assert config["results"]["circuit_breaker_open"] is True
    assert config["results"]["exit_code"] == 3


def test_batch_limit_through_cli_keeps_writing_lines(cli, tmp_path):
    env = {"LLM_PROVIDER": "fake", "MAX_LLM_CALLS_PER_BATCH": "2"}
    code, rows, traces, err = _cli_run(cli, tmp_path, _cases(tmp_path, 5), env)
    assert code == 0
    assert len(rows) == 5
    assert [t["error_class"] for t in traces] == [None, None] + ["batch_limit"] * 3
    assert err.count("MAX_LLM_CALLS_PER_BATCH") == 1


def test_one_crashing_case_does_not_abort_the_batch(cli, tmp_path):
    # The script runs out after the first case: FakeScriptExhausted is an unexpected exception.
    script = _script(tmp_path, [_final()])
    env = {"LLM_PROVIDER": "fake", "FAKE_LLM_SCRIPT": str(script)}
    code, rows, traces, err = _cli_run(cli, tmp_path, _cases(tmp_path, 3), env)
    assert code == 0
    assert len(rows) == 3
    assert [t["error_class"] for t in traces] == [None, "internal_error", "internal_error"]
    assert rows[1]["answer"] == SAFE_FAILURE_ANSWER
    assert "FakeScriptExhausted" in err


def test_primary_cooldown_through_cli_is_traced(cli, tmp_path):
    # Two consecutive primary overloads (cases k0, k1): later cases start on the fallback.
    steps = [_err("overloaded"), _final(), _err("overloaded"), _final(), _final(), _final()]
    env = {
        "LLM_PROVIDER": "fake",
        "FAKE_LLM_SCRIPT": str(_script(tmp_path, steps)),
        "LLM_MAX_ATTEMPTS": "3",
    }
    code, rows, traces, _ = _cli_run(cli, tmp_path, _cases(tmp_path, 4), env)
    assert code == 0
    assert [t["error_class"] for t in traces] == [None] * 4
    first_attempts = [t["llm_calls"][0]["attempts"] for t in traces]
    assert [[(a["reason"], a["status"]) for a in att] for att in first_attempts[:2]] == [
        [("primary", "fallback"), ("failover", "ok")]
    ] * 2
    for att in first_attempts[2:]:
        assert [(a["model"], a["reason"]) for a in att] == [
            ("fake:gemini-3.1-flash-lite", "primary_cooldown")
        ]
    assert all(t["fallback_used"] for t in traces)
    assert all(r["answer"] != SAFE_FAILURE_ANSWER for r in rows)


def test_mixed_failures_batch_continues(cli, tmp_path):
    steps = [
        _err("bad_request"),  # k0 → safe failure
        _err("rate_limit_minute"),  # k1 → retry ...
        _final(),  # ... recovers
        _err("blocked_safety"),  # k2 → safe failure
        _final(),  # k3 ok
    ]
    env = {"LLM_PROVIDER": "fake", "FAKE_LLM_SCRIPT": str(_script(tmp_path, steps))}
    code, rows, traces, _ = _cli_run(cli, tmp_path, _cases(tmp_path, 4), env)
    assert code == 0
    assert [t["error_class"] for t in traces] == ["bad_request", None, "blocked_safety", None]
    assert [r["route"] for r in rows] == ["escalate", "policy", "escalate", "policy"]
