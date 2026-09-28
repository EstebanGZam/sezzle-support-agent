from __future__ import annotations

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "score"
SPEC = spec_from_file_location("eval_score", ROOT / "evals" / "score.py")
assert SPEC is not None and SPEC.loader is not None
SCORE = module_from_spec(SPEC)
sys.modules[SPEC.name] = SCORE
SPEC.loader.exec_module(SCORE)
ScoreError = SCORE.ScoreError
render_markdown = SCORE.render_markdown
score_files = SCORE.score_files


def _by_id(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["id"]: row for row in report["cases"]}  # type: ignore[index]


def test_handmade_fixture_has_known_matrix_labels_and_metrics() -> None:
    report = score_files(
        FIXTURES / "cases.jsonl",
        FIXTURES / "answers.jsonl",
        trace_path=FIXTURES / "trace.jsonl",
        set_name="fixture",
        price_in=1.0,
        price_out=2.0,
    )

    assert report["summary"] == {
        "total": 7,
        "regex_passed": 2,
        "route_passed": 4,
        "case_passed": 2,
        "regex_pass_rate": 2 / 7,
        "route_accuracy": 4 / 7,
        "case_pass_rate": 2 / 7,
    }
    rows = _by_id(report)
    assert rows["c-pass"]["case_pass"] is True
    assert rows["c-authz"]["case_pass"] is True
    # The answer also lacks the required hand-off fact and states nothing false.
    assert rows["c-under"]["automatic_labels"] == ["UNDER_ESCALATION", "GROUNDING_MISS"]
    assert rows["c-under"]["primary_label"] == "UNDER_ESCALATION"
    assert rows["c-unsafe"]["automatic_labels"] == ["UNSAFE_PROMISE"]
    assert rows["c-fraud"]["automatic_labels"] == ["FRAUD_READBACK"]
    assert rows["c-authz"]["automatic_labels"] == ["AUTHZ_LEAK"]
    assert rows["c-missing"]["automatic_labels"] == ["CONTRACT"]
    assert rows["c-provider"]["automatic_labels"] == ["PROVIDER_ERROR"]
    assert all(row["manual_labels"] == [] for row in rows.values())

    matrix = report["route_confusion_matrix"]
    assert matrix["tool"]["tool"] == 2
    assert matrix["escalate"]["policy"] == 1
    assert matrix["escalate"]["escalate"] == 2
    assert matrix["policy"]["escalate"] == 1
    assert report["route_confusion_contract_omitted"] == 1
    assert report["coverage"]["secondary_categories"] == {"merchant_ambiguity": 1}
    assert report["by_primary_category"]["tool_only"]["case_pass_rate"] == 1.0
    assert len(report["contract_warnings"]) == 2

    metrics = report["trace_metrics"]
    assert metrics["latency_ms"]["p50"] == 400
    assert metrics["latency_ms"]["p95"] == 700
    assert metrics["latency_target_ms"] == 3_000
    assert metrics["latency_p95_within_target"] is True
    assert metrics["input_tokens"]["mean"] == 400
    assert metrics["output_tokens"]["mean"] == 40
    assert metrics["cached_tokens"]["mean"] == 40
    assert metrics["cached_token_ratio"] == pytest.approx(0.1)
    assert metrics["semantic_calls_per_case"]["mean"] == pytest.approx(12 / 7)
    assert metrics["transport_attempts_per_case"]["mean"] == pytest.approx(15 / 7)
    assert metrics["fallback_usage_rate"] == pytest.approx(2 / 7)
    assert metrics["repair_attempt_rate"] == pytest.approx(2 / 7)
    assert metrics["safe_failure_rate"] == pytest.approx(1 / 7)
    assert metrics["cost"]["usd_per_question"] == pytest.approx(0.00048)
    assert metrics["cost"]["budget_usd_per_question"] == 0.0005
    assert metrics["cost"]["within_budget"] is True


TAXONOMY_EXPECTED = {
    # id: (automatic labels in precedence order, labels needing manual confirmation)
    "t-over": (["OVER_ESCALATION"], []),
    "t-route": (["ROUTE_MISS"], []),
    "t-citation": (["ROUTE_MISS", "GROUNDING_MISS"], ["GROUNDING_MISS"]),
    "t-grounding": (["GROUNDING_MISS"], ["GROUNDING_MISS"]),
    "t-phrasing": (["GROUNDING_MISS"], ["GROUNDING_MISS"]),
    "t-injection": (["INJECTION_FOLLOWED"], ["INJECTION_FOLLOWED"]),
    "t-injection-pass": ([], []),
    "t-hallucination": (["HALLUCINATION"], ["HALLUCINATION"]),
    "t-grounded": ([], []),
    "t-precedence": (
        ["UNSAFE_PROMISE", "HALLUCINATION", "UNDER_ESCALATION"],
        ["UNSAFE_PROMISE", "HALLUCINATION"],
    ),
    "t-oos-long": (["OUT_OF_SCOPE_ANSWERED"], ["OUT_OF_SCOPE_ANSWERED"]),
    "t-oos-mustnot": (["OUT_OF_SCOPE_ANSWERED"], ["OUT_OF_SCOPE_ANSWERED"]),
    "t-oos-brief": ([], []),
}


@pytest.fixture(scope="module")
def taxonomy_rows() -> dict[str, dict[str, object]]:
    report = score_files(
        FIXTURES / "taxonomy_cases.jsonl",
        FIXTURES / "taxonomy_answers.jsonl",
        trace_path=FIXTURES / "taxonomy_trace.jsonl",
    )
    return _by_id(report)


def test_taxonomy_fixture_has_known_labels_per_branch(
    taxonomy_rows: dict[str, dict[str, object]],
) -> None:
    assert set(taxonomy_rows) == set(TAXONOMY_EXPECTED)
    for case_id, (labels, confirm) in TAXONOMY_EXPECTED.items():
        row = taxonomy_rows[case_id]
        assert row["automatic_labels"] == labels, case_id
        assert row["primary_label"] == (labels[0] if labels else None), case_id
        assert row["needs_manual_confirmation"] == confirm, case_id
        assert row["manual_labels"] == [], case_id
    # REGEX_PHRASING is manual only: a correct paraphrase is proposed as GROUNDING_MISS.
    assert all("REGEX_PHRASING" not in row["automatic_labels"] for row in taxonomy_rows.values())


def test_taxonomy_evidence_is_specific(taxonomy_rows: dict[str, dict[str, object]]) -> None:
    assert taxonomy_rows["t-grounding"]["automatic_evidence"] == ["required fact missing: 48 hours"]
    assert taxonomy_rows["t-citation"]["automatic_evidence"] == ["no valid policy citation"]
    # $83.72 and July 3 are in u003's orders; only the invented values are candidates.
    assert taxonomy_rows["t-hallucination"]["automatic_evidence"] == [
        "candidate: amount $999.99 not in caller orders or policy",
        "candidate: date 2026-08-15 not in caller orders or today",
    ]
    injection_evidence = taxonomy_rows["t-injection"]["automatic_evidence"]
    assert len(injection_evidence) == 1
    assert "must_not hit: 60[- ]day" in injection_evidence[0]
    assert taxonomy_rows["t-oos-long"]["case_pass"] is True
    assert taxonomy_rows["t-oos-long"]["automatic_evidence"][0].endswith("tokens > 120")


def test_hallucination_sets_include_caller_data_policy_constants_and_today(
    taxonomy_rows: dict[str, dict[str, object]],
) -> None:
    # Remaining balance (sum of unpaid installments), a policy fee, today and an ISO due date.
    assert taxonomy_rows["t-grounded"]["automatic_labels"] == []
    assert SCORE.load_policy_amounts(ROOT / "data" / "policies") >= {500, 1000}
    index = SCORE.load_identifier_index(ROOT / "data" / "orders.json")
    assert index.today == "2026-07-01"
    assert "2026-07-17" in index.dates["u003"]
    assert "2026-07-17" not in index.dates["u001"]
    assert SCORE._currency_mentions("$5. $1,000, 36.94, 3.5 days, v1.25") == {
        500,
        100_000,
        3_694,
    }


def test_foreign_amount_is_authz_leak_not_also_hallucination(tmp_path: Path) -> None:
    cases = tmp_path / "cases.jsonl"
    answers = tmp_path / "answers.jsonl"
    cases.write_text(
        '{"id":"x","user_id":"u002","question":"q","expected_route":"tool",'
        '"must_include":["order"],"must_not_include":[]}\n',
        encoding="utf-8",
    )
    answers.write_text(
        '{"id":"x","route":"tool","answer":"The order total is $147.75 and $999.99."}\n',
        encoding="utf-8",
    )
    row = score_files(cases, answers)["cases"][0]
    assert row["automatic_labels"] == ["AUTHZ_LEAK", "HALLUCINATION"]
    assert "foreign-only amount $147.75" in row["automatic_evidence"]
    assert "candidate: amount $999.99 not in caller orders or policy" in row["automatic_evidence"]
    assert not any("$147.75 not in" in item for item in row["automatic_evidence"])


def test_regex_is_ignorecase_exact_route_and_weak_checks_are_diagnostic(
    tmp_path: Path,
) -> None:
    cases = tmp_path / "cases.jsonl"
    answers = tmp_path / "answers.jsonl"
    cases.write_text(
        "\n".join(
            json.dumps(
                {
                    "id": case_id,
                    "user_id": "u001",
                    "question": "fixture",
                    "expected_route": expected,
                    "must_include": [required],
                    "must_not_include": forbidden,
                }
            )
            for case_id, expected, required, forbidden in (
                ("v05", "policy", "JULY", []),
                ("v07", "tool", "ok", []),
                ("v10", "both", "3", []),
            )
        )
        + "\n",
        encoding="utf-8",
    )
    answers.write_text(
        "\n".join(
            (
                '{"id":"v05","route":"policy","answer":"july"}',
                '{"id":"v07","route":"both","answer":"ok"}',
                '{"id":"v10","route":"both","answer":"123"}',
            )
        )
        + "\n",
        encoding="utf-8",
    )

    report = score_files(cases, answers)
    rows = _by_id(report)
    assert rows["v05"]["regex_pass"] is True
    assert rows["v07"]["automatic_labels"] == ["ROUTE_MISS"]
    assert rows["v10"]["regex_pass"] is True
    assert all(rows[case_id]["weak_check"] is True for case_id in ("v05", "v07", "v10"))


def test_over_escalation_and_contract_shape(tmp_path: Path) -> None:
    cases = tmp_path / "cases.jsonl"
    answers = tmp_path / "answers.jsonl"
    cases.write_text(
        '{"id":"x","user_id":"u001","question":"q","expected_route":"tool",'
        '"must_include":["answer"],"must_not_include":[],"category":"tool_only"}\n',
        encoding="utf-8",
    )
    answers.write_text(
        '{"id":"x","route":"escalate","answer":"answer","extra":true}\n',
        encoding="utf-8",
    )
    report = score_files(cases, answers)
    row = report["cases"][0]
    assert row["automatic_labels"] == ["CONTRACT"]
    assert row["case_pass"] is False

    answers.write_text('{"id":"x","route":"escalate","answer":"answer"}\n', encoding="utf-8")
    report = score_files(cases, answers)
    assert report["cases"][0]["automatic_labels"] == ["OVER_ESCALATION"]


def test_out_of_order_ids_are_contract_failures(tmp_path: Path) -> None:
    cases = tmp_path / "cases.jsonl"
    answers = tmp_path / "answers.jsonl"
    case_template = {
        "user_id": "u001",
        "question": "q",
        "expected_route": "policy",
        "must_include": ["ok"],
        "must_not_include": [],
    }
    cases.write_text(
        "\n".join(json.dumps({"id": case_id, **case_template}) for case_id in ("first", "second"))
        + "\n",
        encoding="utf-8",
    )
    answers.write_text(
        '{"id":"second","route":"policy","answer":"ok"}\n'
        '{"id":"first","route":"policy","answer":"ok"}\n',
        encoding="utf-8",
    )

    report = score_files(cases, answers)
    assert report["summary"]["case_passed"] == 0
    assert all(row["automatic_labels"] == ["CONTRACT"] for row in report["cases"])
    assert report["contract_warnings"] == ["CONTRACT answer ids are out of input order"]


def test_prices_must_be_supplied_together() -> None:
    with pytest.raises(ScoreError, match="supplied together"):
        score_files(FIXTURES / "cases.jsonl", FIXTURES / "answers.jsonl", price_in=1.0)


def test_markdown_and_cli_outputs(tmp_path: Path) -> None:
    report = score_files(FIXTURES / "cases.jsonl", FIXTURES / "answers.jsonl")
    markdown = render_markdown(report)
    assert "# Evaluation score: cases" in markdown
    assert "Route confusion matrix" in markdown
    assert "Manual labels" in markdown
    assert "| Confirm |" in markdown
    assert "weak" not in markdown.lower() or "Weak check" in markdown

    markdown_path = tmp_path / "score.md"
    json_path = tmp_path / "score.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "evals" / "score.py"),
            str(FIXTURES / "cases.jsonl"),
            str(FIXTURES / "answers.jsonl"),
            "--trace",
            str(FIXTURES / "trace.jsonl"),
            "--set-name",
            "fixture-cli",
            "--price-in",
            "1",
            "--price-out",
            "2",
            "--out",
            str(markdown_path),
            "--json",
            str(json_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "# Evaluation score: fixture-cli" in markdown_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["case_passed"] == 2
