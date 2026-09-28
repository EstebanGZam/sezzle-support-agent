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
