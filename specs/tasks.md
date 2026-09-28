# Task Breakdown & Traceability

Requirement → Task → Code → Test → Eval. Each task is executed through the prompt listed in `docs/implementation-prompts.md`. **Definition of done:** acceptance criteria met, verification command green, deviations reported, trace/evidence preserved, Conventional Commit referencing the task (e.g. `feat(tools): scoped read-only order lookup [T-05]`). Code that has only been generated is not done.

Agents: **IMP** = principal implementer (Claude, worktree) · **EVAL** = evaluation agent (separate worktree) · **REV** = Codex independent reviewer (read-only) · **LEAD** = Orchestrator lead · **OWNER** = project owner.

| Task | Description | Requirements | Files (sole owner) | Tests / verification | Agent | Prompt | Depends | Status |
|---|---|---|---|---|---|---|---|---|
| T-01 | Scaffold: `pyproject.toml` (Python 3.12; runtime `google-genai>=2.25,<3`, `pydantic>=2`; dev `pytest`, `ruff`), `uv.lock`, `requirements.txt` via `uv export`, package skeleton, ruff config | OWN-01, OWN-08 | `pyproject.toml`, `uv.lock`, `requirements.txt`, `src/support_agent/__init__.py`, `src/support_agent/llm/__init__.py` (empty) | `uv sync --locked && uv run ruff check . && uv run pytest -q` (empty suite ok) | IMP | IP-01 | — | todo |
| T-02 | `config.py` Settings from env (architecture §8), frozen, no key logging | OWN-02, OWN-06, SEC-07, SEC-13 | `src/support_agent/config.py`, `tests/test_config.py` | defaults; missing key → clear error only when provider=gemini; `repr` hides key | IMP | IP-01 | T-01 | todo |
| T-03 | `resources.py`: `PolicyCorpus` (POL-01..12, stable order), `OrdersRepository` (strict Pydantic models), `today` | SEZ-F06, OWN-03, OWN-04 | `src/support_agent/resources.py`, `tests/test_resources.py` | 12 policies; 23 orders; 8 users; today = 2026-07-01; immutability; bad data → validation error | IMP | IP-02 | T-01 | todo |
| T-04 | `facts.py`: neutral facts (architecture §4) | ADR-1, SEZ-F03 | `src/support_agent/facts.py`, `tests/test_facts.py` | next upcoming, unpaid balance, business days (Mon–Fri), paused/failed lists; clock-independence (patched clock) | IMP | IP-02 | T-03 | todo |
| T-05 | `tools.py`: `build_toolset(user_id, repo, today)`; `get_my_orders(order_id?, merchant?)`; schema; parity | SEC-01, SEC-02, SEC-03, SEC-04 | `src/support_agent/tools.py`, `tests/test_tools.py` | no user param in schema; foreign == nonexistent payload (byte-identical); merchant multi-match; unknown user → not_found; invalid order_id pattern → not_found | IMP | IP-03 | T-03, T-04 | todo |
| T-06 | `prompts.py`: static system prefix (scope, rules, voice, output contract) + policy block + `PROMPT_VERSION`; case message template with untrusted delimiters | SEZ-F02, SEZ-F04, SEZ-F05, SEZ-P*, SEC-08, OWN-10 | `src/support_agent/prompts.py`, `tests/test_prompts.py` | prefix byte-identical across cases; all 12 IDs present; no golden-case strings (grep test) | IMP | IP-05 | T-03 | todo |
| T-07 | `llm/base.py` protocol + normalized types + `ProviderError` kinds; `llm/fake.py` scripted fake (sequences, injected errors) | OWN-02, OWN-07 | `src/support_agent/llm/{__init__,base,fake}.py`, `tests/test_fake_llm.py` | fake replays scripts deterministically; error injection per kind | IMP | IP-04 | T-02 | todo |
| T-08 | `llm/gemini.py`: google-genai adapter — AFC disabled, tool mode auto/none, response schema, thinking level, timeout, SDK retries off, own retry + fallback per architecture §7, raw model turn preserved | OWN-02, OWN-06, SEC-07 | `src/support_agent/llm/gemini.py`, `tests/test_gemini_errors.py` | error classification unit-tested with stubbed SDK exceptions (no network); optional `-m live` smoke marked and skipped by default | IMP | IP-04 | T-07 | todo |
| T-09 | `guards.py`: InputGuard, Tripwire (generic vocab), OutputValidator (security §4) | SEZ-F04, SEC-05, SEC-06, SEC-09, SEC-11 | `src/support_agent/guards.py`, `tests/test_guards.py`, `tests/test_validator.py` | the must-pass / must-fail fixtures listed in `specs/security.md` §4; tripwire fires on synthetic request phrasings and not on informational questions | IMP | IP-05 | T-03, T-05 | todo |
| T-10 | `agent.py` loop (architecture §5) + `routing.py` + `trace.py` + `run_cases.py` CLI | SEZ-C01..C04, SEZ-F01, SEZ-F04, SEZ-F05, SEC-07, SEC-10, SEC-12, OWN-04, OWN-14, OWN-15 | `src/support_agent/{agent,routing,trace}.py`, `run_cases.py`, `tests/test_{loop,routing,contract,failures,isolation,no_canned_answers}.py` | FakeLLM end-to-end: direct answer, tool+answer, 2nd tool call ignored, call #2 tool mode `none`, repair path, safe failure, circuit breaker + exit code 3, 4-route table incl. forced_reason precedence, contract shape, cross-case isolation; offline CLI run with the default fake responder | IMP | IP-06 | T-02..T-09 | todo |
| T-11 | CI: `.github/workflows/ci.yml` — gitleaks → `uv sync --locked` → ruff check/format → pytest with `LLM_PROVIDER=fake` | OWN-07, OWN-08, SEC-13 | `.github/workflows/ci.yml` | workflow lint by review; runs green on first push (if remote authorized) | IMP | IP-07 | T-10 | todo |
| T-18 | `evals/score.py` per `specs/evaluation.md` (regex re.I, route match, categories, failure tags, latency/tokens/$ from trace) + `evals/README.md` | OWN-07, SEZ-D03 | `evals/score.py`, `evals/README.md`, `tests/test_score.py` | scores a hand-made answers file with known expected results | EVAL | E-01 | T-01 (parallel to T-02..T-10) | todo |
| T-12 | Independent review of the full diff vs specs (SEZ-F01 no canned answers, SEC-*, overfitting grep, secrets) | SEZ-F01, SEZ-F07, OWN-12, SEC-* | review notes → `docs/reviews/R-01.md` | findings resolved or accepted by LEAD/OWNER | REV | R-01 | T-10, T-18 | todo |
| T-13 | Baseline run `evals/runs/001_baseline` on golden + adversarial_dev with the real model; commit unedited | SEZ-D03, SEZ-L01, SEZ-L02, SEZ-F02..F05, OWN-16 | `evals/runs/001_baseline/*` | score.md generated; failures tagged | EVAL (runs) + LEAD | E-02 | T-12, **A-10 billing confirmed** | todo |
| T-14 | Iteration loop: one hypothesis → one change (by IMP) → rerun → delta; final run incl. holdout copied in; `ITERATION.md` with failure taxonomy | SEZ-D03, SEZ-L01..L03, SEZ-F07, OWN-12 | code per change; `evals/runs/NNN_*`; `ITERATION.md` | delta tables; holdout reported honestly | IMP + EVAL | IP-08 / E-03 | T-13 | todo |
| T-15 | Finalize `DECISIONS.md` with measured numbers (replace every `[MEASURE]`) | SEZ-D02, SEZ-N01, SEZ-L02, SEZ-L03, OWN-11, OWN-16 | `DECISIONS.md` | exactly 3 ADRs, ≤ ~10 lines, 4 parts each | LEAD (+ OWNER approval) | D-01 | T-14 | todo |
| T-16 | `PROMPTS.md` (planning, agent, system, eval prompts) + `README.md` (run + unfinished) | SEZ-D04, SEZ-D05 | `PROMPTS.md`, `README.md` | sections present; README ≤ ~35 lines | LEAD | D-01 | T-14 | todo |
| T-17 | Delivery: secret scan, zip build from clean checkout, verify `sha256sum -c`, run fake-mode tests from the unzipped copy; private push only if authorized | SEZ-S01, SEZ-S02, OWN-08, SEC-13 | `scripts/make_zip.sh` (optional) | zip runs `uv run pytest -q` in a temp dir; no `.env` in archive | LEAD | X-01 | T-15, T-16 | todo |

## Scope tiers & cut order (review R-00 #12)
The owner manages the clock; these tiers tell agents what to protect when time runs short.
- **Tier 1 — must ship:**
  - T-01..T-06, T-09 (validator *core*: `schema`, `order_id`, `action_claim`, `commitment`, `limit_disclosure`), T-10.
  - Minimal T-07/T-08: single model, one retry, auth fail-fast.
  - T-13 baseline, one measured iteration + final visible run (T-14), T-15, T-16.
- **Tier 2 — should:**
  - Fallback model + circuit breaker; the `amount_ungrounded` / `date_ungrounded` / `escalation_coherence` checks; the `human_only_action` tripwire category; T-18 scorer automation beyond pass/fail + route.
  - Holdout final run; R-01 review.
- **Tier 3 — cut first**, in this order:
  1. CI (T-11) and zip automation (T-17 script — a manual `git archive` is fine).
  2. Automated failure-label assignment and noise-floor rerun (manual tagging in `score.md` is acceptable).
  3. Derived-fact breadth beyond `next_upcoming_installment`, `unpaid_balance`, `business_days_since_issued`.
  4. Concurrency.

  Every cut is listed in README "Unfinished".

## Traceability matrix (every SEZ requirement → task → verification)
| Requirement | Tasks | Verification |
|---|---|---|
| SEZ-C01..C04 | T-10 | `tests/test_contract.py`, `tests/test_routing.py` |
| SEZ-F01 | T-10, T-12 | `tests/test_no_canned_answers.py`, R-01 review |
| SEZ-F02 | T-03, T-06, T-13/T-14 | categories `policy_only`, `multi_intent`; golden v02/v08 |
| SEZ-F03 | T-04, T-05, T-13/T-14 | `tests/test_tools.py`; golden v01/v03/v04/v10; category `tool_only` |
| SEZ-F04, SEZ-F05 | T-06, T-09, T-10, T-13/T-14 | golden v05–v07, v09; escalation categories |
| SEZ-F06 | T-03, T-04 | `tests/test_facts.py` (patched clock) |
| SEZ-F07 | T-06, T-12, T-14 | grep test in `tests/test_prompts.py`; holdout result |
| SEZ-P01..P12 | T-06 (prompt), T-13/T-14 (eval) | golden + adversarial categories per `specs/evaluation.md` §3 |
| SEZ-N01, SEZ-L03 | T-15 (+ T-13/T-14 measurements) | ADR-3 review |
| SEZ-L01, SEZ-L02 | T-05, T-09, T-13, T-14, T-15 | eval results; ADR alternatives |
| SEZ-D01..D05 | T-10, T-13..T-16 | deliverable checks in `docs/readiness-checklist.md` §E |
| SEZ-S01, SEZ-S02 | T-17 | zip check; repo visibility |
| SEZ-T01 | — | owner-managed |

## Traceability notes
- SEZ-P* are verified by eval categories (T-13/T-14) and prompt content (T-06); no code task decides policy outcomes (ADR-1).
- SEZ-T01 (time) is owner-managed.
- OWN-09 (agent roles) is a process requirement, verified in `docs/agent-plan.md` and PROMPTS.md.
- OWN-13 (no deploy) is satisfied by absence.
