# Sequential Implementation Prompts

Short, one-stage prompts. Before dispatch, the owner must have approved the AR bundle (AR-01…AR-07) and set the primary model (OD-15).

Short, one-stage prompts. The LEAD dispatches them in order (IMP prompts sequentially in one worktree; EVAL prompts in parallel in a separate worktree). Each prompt is sent verbatim, prefixed by the common header. The exact text sent is logged in `PROMPTS.md`. **Do not dispatch any prompt until the owner authorizes implementation.**

## Common header (prepended to every IMP/EVAL prompt)
```
Read AGENTS.md first and follow its execution protocol. Implement ONLY the task(s) named below, touching ONLY the listed files.
Before coding, state your plan and the requirement IDs you implement. When done, report: acceptance criteria with evidence,
verification output of the FULL gate `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` (plus any task-specific command),
deviations from specs, open issues. Commit with a Conventional Commit message including the task ID.
Never read /home/esteban/Documents/Sezzle/holdout/. No real LLM calls unless the prompt says so.
```

---

### IP-01 — Scaffold + config (IMP · T-01, T-02)
- **Read:** `specs/tasks.md` T-01/T-02, `specs/architecture.md` §2 and §8.
- **Do:**
  - Create `pyproject.toml` (Python `>=3.12,<3.13`; deps `google-genai>=2.25,<3`, `pydantic>=2,<3`; dev group `pytest`, `ruff`), `uv.lock`, `requirements.txt` (`uv export --no-dev --no-hashes`), ruff config, and `src/support_agent/__init__.py` + empty `src/support_agent/llm/__init__.py` (the only package files T-01 owns; other modules are created by their own tasks).
  - Implement `config.py` `Settings`.
- **Acceptance:**
  - `uv sync --locked` works.
  - `Settings.from_env()` defaults match architecture §8.
  - With `LLM_PROVIDER=gemini`, a missing `GEMINI_PRIMARY_MODEL` or key raises a clear config error (the CLI maps it to exit 2).
  - With `fake`, neither is required.
  - `repr(settings)` never shows the key.
  - `tests/test_config.py` passes.
- **Verify:** `uv run ruff check . && uv run pytest -q`
- **Out of scope:** any LLM, tool, or agent logic.

### IP-02 — Resources + neutral facts (IMP · T-03, T-04)
- **Read:** architecture §2 and §4; `data/orders.json`; A-05, A-06, A-07, A-14. [AR-04: neutral facts only]
- **Do:** implement `resources.py` (strict Pydantic models for users/orders/installments/refund; `PolicyCorpus` with IDs `POL-01..12` from the file-name numbers, titles from `# ` headings) and `facts.py` (neutral facts only; no policy thresholds).
- **Acceptance:**
  - 12 policies, 23 orders, 8 users, today 2026-07-01.
  - Resources are immutable.
  - Facts are correct on hand-checked orders (e.g. ord_3006 next upcoming = installment 4, 118.36, due 2026-07-11).
  - Business days are Mon–Fri.
  - Tests pass with the system clock patched.
- **Verify:** `uv run pytest -q tests/test_resources.py tests/test_facts.py`
- **Out of scope:** eligibility or fee conclusions (ADR-1).

### IP-03 — Scoped read-only tool (IMP · T-05)
- **Read:** architecture §3.2; security §2 (LLM02); SEC-01..04.
- **Do:** implement `build_toolset(user_id, repo, today)` returning the `get_my_orders` declaration (JSON schema) + executor.
- **Acceptance:**
  - Schema has no user field.
  - Filter by the caller before matching.
  - Foreign and nonexistent IDs return byte-identical payloads.
  - Merchant matching returns all of the caller's matches.
  - Unknown user → `not_found`.
  - A malformed `order_id` is treated as no match.
  - Result includes `facts`.
- **Verify:** `uv run pytest -q tests/test_tools.py`

### IP-04 — LLM protocol, fake, Gemini adapter (IMP · T-07, T-08)
- **Read:** architecture §3.4, §7, §8; `docs/planning/smoke-test/` (tools + JSON schema combine on 3.x Flash-Lite; echo the model turn unchanged).
- **Do:** implement `llm/base.py` (protocol, request/response types, `ProviderError` kinds), `llm/fake.py` (scripted sequences + injected errors), and `llm/gemini.py` (google-genai; AFC disabled; tool mode auto/none; response schema; `thinking_level`; timeout; SDK retries off; own retry/fallback table; usage incl. cached tokens).
- **Acceptance:**
  - Every row of the architecture §7 table is unit-tested with stubbed exceptions: `error_class`, same-model retry, fallback eligibility.
  - Auth/billing errors are never retried.
  - Semantic calls vs transport attempts are counted as defined.
  - The default fake responder and `FAKE_LLM_SCRIPT` replay work.
  - An optional live test is marked `@pytest.mark.live` and skipped by default.
- **Verify:** `uv run pytest -q tests/test_fake_llm.py tests/test_gemini_errors.py`
- **Out of scope:** real API calls.

### IP-05 — Prompts + guards (IMP · T-06, T-09)
- **Read:** architecture §5; security §3–§5; `docs/planning/research/brand-report.md` §(b) voice rules; SEZ-P01..P12.
- **Do:**
  - `prompts.py`: static prefix covering domain scope, grounding rules (policy text + tool data only), escalation guidance per policy family, voice, citation guidance ("cite a policy only when its rule justifies the answer"), and the output contract; all policies as `[POL-NN]`; `PROMPT_VERSION`.
  - Case message template with `<shopper_message>` delimiters.
  - `guards.py`: InputGuard, Tripwire (four categories, precision-first, security §3), OutputValidator (typed checks from security §4).
- **Acceptance:**
  - The prefix is byte-identical across cases.
  - A grep test proves no golden/adversarial question text is in `src/`.
  - All must-pass / must-fail fixtures from security §4 are covered.
  - The tripwire fires on synthetic request phrasings and not on informational questions.
  - The tripwire never produces answer text.
- **Verify:** `uv run pytest -q tests/test_prompts.py tests/test_guards.py tests/test_validator.py`

### IP-06 — Agent loop, routing, trace, CLI (IMP · T-10)
- **Read:** architecture §1, §5, §6, §10; `specs/evaluation.md` trace schema; SEZ-C01..C04, OWN-14, OWN-15.
- **Do:** implement `agent.answer_case`, `routing.derive_route`, `trace.TraceRecord`, and `run_cases.py`.
- **Acceptance (all with FakeLLM):**
  - The direct-answer path works.
  - The tool→answer path works.
  - A second tool call is ignored and recorded.
  - Call #2 uses tool mode `none`.
  - Repair path, then safe failure.
  - The 4-route table passes (architecture §6), including `forced_reason` precedence and `policy_applied`.
  - The auth/billing circuit breaker writes all lines and exits 3.
  - Contract shape is exactly `{id, route, answer}`.
  - Extra input keys are ignored.
  - One failing case doesn't abort the batch.
  - u001→u002 isolation holds.
  - No canned substantive answers exist.
- **Verify:** the full gate, plus `LLM_PROVIDER=fake uv run python run_cases.py cases/golden_visible.jsonl /tmp/fake_answers.jsonl`. This uses the default fake responder (architecture §8), so it produces 10 lines with route `policy`.

### IP-07 — CI (IMP · T-11)
- **Do:** add `.github/workflows/ci.yml`: checkout (fetch-depth 0) → gitleaks → setup-uv → `uv sync --locked` → ruff check + format check → `pytest -q` with `LLM_PROVIDER=fake`; `permissions: contents: read`.
- **Acceptance:** YAML valid; no secrets required.
- **Verify:** `uv run pytest -q` is green locally; the LEAD reviews the YAML. The workflow first runs on the first owner-authorized push.

---

### E-01 — Scorer (EVAL · T-18, parallel with IP-02..IP-06)
- **Read:** `specs/evaluation.md`.
- **Do:** implement `evals/score.py` (+ `evals/README.md`, `tests/test_score.py`) exactly per the scoring spec: regex `re.I`, route match reported separately, per-set/per-category aggregates, failure tags (auto where defined), and latency/tokens/$ from the trace (model price from a CLI flag or config, not hard-coded).
- **Acceptance:** scoring a hand-made answers file reproduces the expected pass/fail matrix; markdown `score.md` output.
- **Verify:** `uv run pytest -q tests/test_score.py`

### R-01 — Independent review (REV · T-12, Codex, read-only)
Review the landed diff against `specs/requirements.md`, `specs/security.md`, ADR-1. Check:
- no canned substantive answers;
- the `user_id` is never model-controlled;
- not-found parity;
- no write tools;
- validator correctness and false-positive risk;
- golden/adversarial strings absent from `src/`;
- no secrets;
- error handling per architecture §7;
- tests actually assert the ACs.

Write findings (severity, file:line, fix) to `docs/reviews/R-01.md`. Do not modify code.

### E-02 — Baseline run (EVAL · T-13) — requires owner authorization + billing confirmed (A-10)
Run the real model once on `cases/golden_visible.jsonl` and `cases/adversarial_dev.jsonl` into `evals/runs/001_baseline/` (`answers.jsonl`, `trace.jsonl`, `config.json` with model ID + `PROMPT_VERSION`), then score. Commit unedited. Tag failures per the taxonomy; list the top failure classes with case IDs.

### IP-08 / E-03 — Iteration (IMP + EVAL · T-14), repeated as needed
Iteration template:
1. **Hypothesis:** failure class X in cases [...] is caused by Y.
2. **One change:** file(s) Z.
3. **Expected effect:** ...
4. **Rerun:** `evals/runs/NNN_label`.
5. **Delta table:** before/after per category.
6. **Regressions.**

Rules: no case-specific hacks; policy-conclusion facts only with this template (ADR-1). Final iteration: EVAL copies the holdout set in, runs once, and commits; no further tuning after seeing holdout results.

### D-01 — Documentation (LEAD · T-15, T-16)
- Replace every `[MEASURE]` in `DECISIONS.md` with measured values.
- Write `ITERATION.md` (first-run failures, taxonomy, changes, deltas, holdout).
- Complete `PROMPTS.md` and `README.md` (run instructions, honest "Unfinished", key assumptions A-04/A-08/A-10).

### X-01 — Delivery (LEAD · T-17)
- Run the secret scan.
- Build the zip from a clean `git archive` (excludes `.env`, `.venv/`), unzip into a temp dir, run `uv sync --locked && uv run pytest -q`, and `sha256sum -c assessment/SHA256SUMS`.
- Push the private repo **only if the owner authorizes**.
