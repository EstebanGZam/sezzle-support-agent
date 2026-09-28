"""CLI contract (SEZ-C01..C04, OWN-14; architecture §3.1) with the offline fake provider."""

import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest

from support_agent.config import PROJECT_ROOT
from support_agent.guards import SAFE_FAILURE_ANSWER

GOLDEN = PROJECT_ROOT / "cases" / "golden_visible.jsonl"
FAKE_ENV = {"LLM_PROVIDER": "fake"}


@pytest.fixture(scope="module")
def cli():
    spec = importlib.util.spec_from_file_location("run_cases_cli", PROJECT_ROOT / "run_cases.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


def _run(cli, cases_path, answers_path, *extra, environ=None):
    err = io.StringIO()
    code = cli.main(
        [str(cases_path), str(answers_path), *extra], environ=environ or FAKE_ENV, stderr=err
    )
    return code, err.getvalue()


def _lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_cases(path, rows):
    path.write_text(
        "".join((r if isinstance(r, str) else json.dumps(r)) + "\n" for r in rows),
        encoding="utf-8",
    )


def test_golden_run_offline_contract_shape(cli, tmp_path):
    answers = tmp_path / "answers.jsonl"
    code, _ = _run(cli, GOLDEN, answers)
    assert code == 0
    rows = _lines(answers)
    golden_ids = [json.loads(line)["id"] for line in GOLDEN.read_text().splitlines()]
    assert [r["id"] for r in rows] == golden_ids  # one line per id, input order
    for row in rows:
        assert list(row) == ["id", "route", "answer"]  # exactly the three keys
        assert row["route"] in {"policy", "tool", "both", "escalate"}
        assert isinstance(row["answer"], str) and row["answer"]
    # Default trace/config next to the answers.
    traces = _lines(tmp_path / "answers.trace.jsonl")
    assert [t["id"] for t in traces] == golden_ids
    config = json.loads((tmp_path / "answers.config.json").read_text())
    assert config["results"]["cases"] == len(golden_ids)


def test_default_fake_responder_routes_policy_unless_tripwire_forces(cli, tmp_path):
    answers = tmp_path / "a.jsonl"
    _run(cli, GOLDEN, answers)
    traces = {t["id"]: t for t in _lines(tmp_path / "a.trace.jsonl")}
    for row in _lines(answers):
        forced = traces[row["id"]]["route_inputs"]["forced_reason"]
        assert row["route"] == ("escalate" if forced else "policy")


def test_extra_input_keys_are_ignored(cli, tmp_path):
    cases = tmp_path / "cases.jsonl"
    base = {"id": "x1", "user_id": "u002", "question": "How does pay in 4 work?"}
    extra = {**base, "id": "x2", "expected_route": "tool", "must_include": ["zzz"], "why": "w"}
    _write_cases(cases, [base, extra])
    answers = tmp_path / "answers.jsonl"
    assert _run(cli, cases, answers)[0] == 0
    first, second = _lines(answers)
    assert (first["route"], first["answer"]) == (second["route"], second["answer"])


def test_blank_and_malformed_lines(cli, tmp_path):
    cases = tmp_path / "cases.jsonl"
    _write_cases(
        cases,
        [
            {"id": "ok1", "user_id": "u001", "question": "How does it work?"},
            "",
            "   ",
            '{"id": "broken1", "user_id": "u001", "question": ',  # not JSON, id readable
            "complete garbage",  # no readable id → skipped
            {"id": "noq", "user_id": "u001"},  # id readable, question missing
            {"id": 7, "question": "numeric id"},  # no readable string id → skipped
            {"id": "ok2", "user_id": "u002", "question": "Hi"},
        ],
    )
    answers = tmp_path / "answers.jsonl"
    code, err = _run(cli, cases, answers)
    assert code == 0
    rows = _lines(answers)
    assert [r["id"] for r in rows] == ["ok1", "broken1", "noq", "ok2"]
    assert rows[1]["answer"] == SAFE_FAILURE_ANSWER and rows[1]["route"] == "escalate"
    assert rows[2]["answer"] == SAFE_FAILURE_ANSWER
    traces = {t["id"]: t for t in _lines(tmp_path / "answers.trace.jsonl")}
    assert traces["broken1"]["error_class"] == "invalid_input"
    assert "skipped" in err


def test_output_is_utf8(cli, tmp_path):
    cases = tmp_path / "cases.jsonl"
    _write_cases(cases, [{"id": "ü-1", "user_id": "u001", "question": "¿Cómo funciona?"}])
    answers = tmp_path / "answers.jsonl"
    assert _run(cli, cases, answers)[0] == 0
    raw = answers.read_bytes().decode("utf-8")
    assert '"ü-1"' in raw


def test_custom_trace_and_config_paths(cli, tmp_path):
    answers = tmp_path / "out" / "answers.jsonl"
    trace = tmp_path / "t" / "trace.jsonl"
    config = tmp_path / "c" / "config.json"
    code, _ = _run(
        cli, GOLDEN, answers, "--trace", str(trace), "--config", str(config), "--run-id", "007_x"
    )
    assert code == 0
    assert all(t["run_id"] == "007_x" for t in _lines(trace))
    assert json.loads(config.read_text())["run_id"] == "007_x"


def test_run_config_fields_and_no_secrets(cli, tmp_path):
    key = "AIzaTESTKEY-never-print-this-0123456789"
    answers = tmp_path / "answers.jsonl"
    code, err = _run(cli, GOLDEN, answers, environ={**FAKE_ENV, "GOOGLE_API_KEY": key})
    assert code == 0
    config = json.loads((tmp_path / "answers.config.json").read_text())
    for field in (
        "primary_model",
        "fallback_model",
        "temperature",
        "max_output_tokens",
        "timeout_s",
        "llm_max_attempts",
        "retry_policy",
        "prompt_version",
        "corpus_hash",
        "git_sha",
        "case_files",
        "run_date",
        "credential_env_var",
        "credential_fingerprint",
        "holdout_contaminated",
    ):
        assert field in config, field
    assert config["credential_env_var"] == "GOOGLE_API_KEY"
    assert len(config["credential_fingerprint"]) == 12
    assert config["holdout_contaminated"] is False
    traces = _lines(tmp_path / "answers.trace.jsonl")
    assert {t["prompt_version"] for t in traces} == {config["prompt_version"]}
    assert {t["corpus_hash"] for t in traces} == {config["corpus_hash"]}
    for path in tmp_path.iterdir():
        assert key not in path.read_text(encoding="utf-8")
    assert key not in err


def test_missing_cases_file_exits_2_and_writes_nothing(cli, tmp_path):
    answers = tmp_path / "answers.jsonl"
    code, err = _run(cli, tmp_path / "nope.jsonl", answers)
    assert code == 2
    assert "not found" in err
    assert list(tmp_path.iterdir()) == []


def test_gemini_without_key_exits_2_and_writes_nothing(cli, tmp_path):
    answers = tmp_path / "answers.jsonl"
    code, err = _run(cli, GOLDEN, answers, environ={"LLM_PROVIDER": "gemini"})
    assert code == 2
    assert "GOOGLE_API_KEY" in err
    assert list(tmp_path.iterdir()) == []


def test_unverified_model_needs_override(cli, tmp_path):
    env = {**FAKE_ENV, "GEMINI_PRIMARY_MODEL": "gemini-9-experimental"}
    answers = tmp_path / "answers.jsonl"
    assert _run(cli, GOLDEN, answers, environ=env)[0] == 2
    assert not answers.exists()
    assert _run(cli, GOLDEN, answers, "--allow-unverified-model", environ=env)[0] == 0
    assert len(_lines(answers)) == 10


def test_settings_warnings_go_to_stderr(cli, tmp_path):
    env = {**FAKE_ENV, "GEMINI_FALLBACK_MODEL": "gemini-3.5-flash-lite"}
    code, err = _run(cli, GOLDEN, tmp_path / "a.jsonl", environ=env)
    assert code == 0
    assert "warning:" in err and "fallback ignored" in err


def test_cli_runs_as_script_from_repo_root(tmp_path):
    """`python3 run_cases.py <cases> <answers>` works without installing the package."""
    answers = tmp_path / "answers.jsonl"
    config_prefixes = (
        "GEMINI_",
        "GOOGLE_",
        "LLM_",
        "FAKE_LLM",
        "MAX_LLM",
        "INPUT_CHAR",
        "DATA_DIR",
    )
    env = {
        k: v
        for k, v in os.environ.items()
        if k != "PYTHONPATH" and not k.startswith(config_prefixes)
    }
    env["LLM_PROVIDER"] = "fake"
    proc = subprocess.run(
        [sys.executable, "run_cases.py", str(GOLDEN), str(answers)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert len(_lines(answers)) == 10
