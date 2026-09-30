#!/usr/bin/env python3
"""CLI contract (architecture §3.1): ``python3 run_cases.py <cases.jsonl> <answers.jsonl>``.

Writes one ``{id, route, answer}`` line per input case (input order), a per-case trace
(``--trace``, default ``<answers>.trace.jsonl``) and a run config (``--config``, default
``<answers>.config.json``). Neither contains secrets: only the credential's env-var name and
fingerprint are recorded (AR-09, SEC-13).

Exit codes: 0 every input line produced an output line (safe failures included); 2 unusable
input/config, nothing written; 3 the auth/billing circuit breaker opened, all lines still written.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_SRC = str(ROOT / "src")
if _SRC not in sys.path:  # the project is not an installable package
    sys.path.insert(0, _SRC)

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
from collections import Counter  # noqa: E402
from collections.abc import Mapping, Sequence  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from typing import Any, TextIO  # noqa: E402

from pydantic import ValidationError  # noqa: E402

from support_agent.agent import (  # noqa: E402
    AgentStatics,
    CallBudget,
    Case,
    CaseResult,
    answer_case,
    safe_failure_result,
)
from support_agent.config import ConfigError, Settings  # noqa: E402
from support_agent.llm import RETRY_TABLE, LLMClient, make_llm_client  # noqa: E402
from support_agent.resources import Resources  # noqa: E402

EXIT_OK = 0
EXIT_UNUSABLE = 2
EXIT_BREAKER = 3

_ID_RE = re.compile(r'"id"\s*:\s*"((?:[^"\\]|\\.){1,200})"')


@dataclass(frozen=True)
class InputEntry:
    """A parsed input line: a usable ``case``, or only the readable ``case_id`` (OWN-14)."""

    line_number: int
    case_id: str
    case: Case | None
    problem: str | None = None


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    llm: LLMClient | None = None,
    stderr: TextIO | None = None,
) -> int:
    err = stderr or sys.stderr
    args = _parse_args(argv)

    cases_path: Path = args.cases
    answers_path: Path = args.answers
    trace_path: Path = args.trace or answers_path.with_suffix(".trace.jsonl")
    config_path: Path = args.config or answers_path.with_suffix(".config.json")
    run_id = args.run_id or answers_path.resolve().parent.name

    # Everything that can make the run unusable is checked before anything is written.
    if not cases_path.is_file():
        print(f"error: cases file not found: {cases_path}", file=err)
        return EXIT_UNUSABLE
    try:
        settings = Settings.from_env(environ, allow_unverified_model=args.allow_unverified_model)
    except ConfigError as exc:
        print(f"error: {exc}", file=err)
        return EXIT_UNUSABLE
    for warning in settings.warnings:
        print(f"warning: {warning}", file=err)
    try:
        resources = Resources.load(settings)
        statics = AgentStatics.build(resources)
        client = llm if llm is not None else make_llm_client(settings)
        cases_bytes = cases_path.read_bytes()
        entries = parse_cases(cases_bytes.decode("utf-8"), err)
    except (ConfigError, OSError, ValueError, ValidationError) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=err)
        return EXIT_UNUSABLE

    for path in (answers_path, trace_path, config_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    budget = CallBudget(settings.max_llm_calls_per_batch)
    breaker_open = False
    batch_limit_reported = False
    results: list[CaseResult] = []
    with (
        answers_path.open("w", encoding="utf-8") as answers_file,
        trace_path.open("w", encoding="utf-8") as trace_file,
    ):
        for entry in entries:
            result = _run_entry(
                entry, resources, client, statics, budget, run_id, breaker_open, err
            )
            if result.error_class == "auth_billing" and not breaker_open:
                breaker_open = True
                print(
                    f"error: auth/billing failure on case {entry.case_id!r}; circuit breaker open, "
                    f"remaining cases get the safe-failure answer without LLM calls. "
                    f"Check {settings.credential_env_var} and the project's billing.",
                    file=err,
                )
            if result.error_class == "batch_limit" and not batch_limit_reported:
                batch_limit_reported = True
                print(
                    f"error: MAX_LLM_CALLS_PER_BATCH={budget.limit} reached at case "
                    f"{entry.case_id!r}; remaining cases get the safe-failure answer.",
                    file=err,
                )
            answers_file.write(json.dumps(result.answer_line(), ensure_ascii=False) + "\n")
            trace_file.write(result.trace.to_json() + "\n")
            answers_file.flush()
            trace_file.flush()
            results.append(result)

    exit_code = EXIT_BREAKER if breaker_open else EXIT_OK
    config = build_run_config(
        settings=settings,
        statics=statics,
        resources=resources,
        run_id=run_id,
        cases_path=cases_path,
        cases_sha256=hashlib.sha256(cases_bytes).hexdigest(),
        answers_path=answers_path,
        trace_path=trace_path,
        holdout_contaminated=args.holdout_contaminated,
        results=results,
        budget=budget,
        exit_code=exit_code,
    )
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return exit_code


def _run_entry(
    entry: InputEntry,
    resources: Resources,
    llm: LLMClient,
    statics: AgentStatics,
    budget: CallBudget,
    run_id: str,
    breaker_open: bool,
    err: TextIO,
) -> CaseResult:
    case = entry.case
    if case is None:
        print(f"warning: line {entry.line_number}: {entry.problem}; safe-failure line", file=err)
        return safe_failure_result(entry.case_id, "", "invalid_input", statics, run_id=run_id)
    if breaker_open:
        return safe_failure_result(case.id, case.user_id, "auth_billing", statics, run_id=run_id)
    try:
        return answer_case(resources, llm, case, statics=statics, budget=budget, run_id=run_id)
    except Exception as exc:  # one failing case must not abort the batch (OWN-15)
        # Only the exception type is reported: messages could echo request data.
        print(f"error: case {case.id!r}: internal error ({type(exc).__name__})", file=err)
        return safe_failure_result(case.id, case.user_id, "internal_error", statics, run_id=run_id)


def parse_cases(text: str, err: TextIO) -> list[InputEntry]:
    """OWN-14: blank lines are skipped; a malformed line with a readable id yields an entry for
    that id (answered with the safe failure), otherwise it is logged and skipped. Extra keys are
    ignored (SEZ-C02)."""
    entries: list[InputEntry] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except ValueError:
            match = _ID_RE.search(line)
            if match:
                case_id = json.loads(f'"{match.group(1)}"')
                entries.append(InputEntry(number, case_id, None, "line is not valid JSON"))
            else:
                print(f"warning: line {number}: not JSON and no readable id; skipped", file=err)
            continue
        if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not data["id"]:
            print(f"warning: line {number}: no readable string id; skipped", file=err)
            continue
        try:
            entries.append(InputEntry(number, data["id"], Case.from_mapping(data)))
        except ValueError as exc:
            entries.append(InputEntry(number, data["id"], None, str(exc)))
    return entries


def build_run_config(
    *,
    settings: Settings,
    statics: AgentStatics,
    resources: Resources,
    run_id: str,
    cases_path: Path,
    cases_sha256: str,
    answers_path: Path,
    trace_path: Path,
    holdout_contaminated: bool,
    results: Sequence[CaseResult],
    budget: CallBudget,
    exit_code: int,
) -> dict[str, Any]:
    """Run ``config.json`` (evaluation §6). Never contains the key, only its fingerprint."""
    error_classes = Counter(r.error_class for r in results if r.error_class is not None)
    return {
        "run_id": run_id,
        "run_date": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": _git(["rev-parse", "HEAD"]),
        "git_dirty": _git_dirty(),
        "provider": settings.provider,
        "primary_model": settings.primary_model,
        "fallback_model": settings.fallback_model,
        "allow_unverified_model": settings.allow_unverified_model,
        "temperature": None,  # not set by the adapter: provider default
        "thinking_level": settings.thinking_level,
        # GroqCloud-only knobs (None for other providers): reasoning effort and client pacing.
        "reasoning_effort": settings.reasoning_effort if settings.provider == "groq" else None,
        "pacing": (
            {
                "tpm_budget": settings.tpm_budget,
                "min_call_interval_s": settings.min_call_interval_s,
            }
            if settings.provider == "groq"
            else None
        ),
        "max_output_tokens": settings.max_output_tokens,
        "timeout_s": settings.timeout_s,
        "llm_max_attempts": settings.max_attempts,
        "retry_policy": {
            kind: {"same_model_retry": rule.same_model_retry, "fallback": rule.fallback_eligible}
            for kind, rule in RETRY_TABLE.items()
        },
        "max_llm_calls_per_batch": settings.max_llm_calls_per_batch,
        "input_char_cap": settings.input_char_cap,
        "fake_llm_script": _display(settings.fake_llm_script) if settings.fake_llm_script else None,
        "prompt_version": statics.prompts.prompt_version,
        "corpus_hash": statics.prompts.corpus_hash,
        "today": resources.today.isoformat(),
        "case_files": {_display(cases_path): cases_sha256},
        "answers_path": _display(answers_path),
        "trace_path": _display(trace_path),
        "credential_env_var": settings.credential_env_var,
        "credential_fingerprint": settings.credential_fingerprint(),
        "holdout_contaminated": holdout_contaminated,
        "results": {
            "cases": len(results),
            "safe_failures": sum(r.safe_failure for r in results),
            "error_classes": dict(sorted(error_classes.items())),
            "routes": dict(sorted(Counter(r.route for r in results).items())),
            "llm_semantic_calls": budget.used,
            "circuit_breaker_open": exit_code == EXIT_BREAKER,
            "exit_code": exit_code,
        },
    }


def _display(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _git(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _git_dirty() -> bool | None:
    status = _git(["status", "--porcelain"])
    return None if status is None else bool(status)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Answer shopper-support cases (JSONL in/out).")
    parser.add_argument("cases", type=Path, help="input cases JSONL ({id, user_id, question})")
    parser.add_argument("answers", type=Path, help="output answers JSONL ({id, route, answer})")
    parser.add_argument("--trace", type=Path, help="trace JSONL (default <answers>.trace.jsonl)")
    parser.add_argument(
        "--config", type=Path, help="run config JSON (default <answers>.config.json)"
    )
    parser.add_argument("--run-id", help="run label for traces (default: answers' parent dir)")
    parser.add_argument(
        "--allow-unverified-model",
        action="store_true",
        help="accept model IDs outside the known tools+JSON-schema-compatible set",
    )
    parser.add_argument(
        "--holdout-contaminated",
        action="store_true",
        help="label this run holdout-contaminated in config.json (evaluation §1)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
