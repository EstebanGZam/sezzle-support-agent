# Architecture Specification

Implements `specs/requirements.md`. The three graded ADRs are in `DECISIONS.md`. Everything here is a specification, not code; agents implement exactly this, and report deviations instead of silently changing it.

**Provenance.** The overall direction is **owner-approved** (OD-01…OD-14 in `docs/decision-log.md`). Design details marked **[AR-nn]** are *agent recommendations*, **proposed** and pending the owner's approval of the AR bundle at implementation start:
- AR-01 one tool round;
- AR-02 route derivation;
- AR-03 validator design;
- AR-04 neutral-facts boundary;
- AR-07 human-only-action tripwire.
- AR-09 explicit key source.

Status of each AR after P-005: `docs/decision-log.md`.

Canonical contracts (answer schema, route rule, error/retry table, trace fields, `PROMPT_VERSION`) are defined **here**, and `specs/evaluation.md` mirrors them.

## 1. Overview

```
run_cases.py (CLI, sequential)
  └─ Resources.load()  ← once: Settings, PolicyCorpus, OrdersRepository, today   [immutable, shared]
  └─ LLMClient         ← once: GeminiClient | FakeLLM                            [shared, stateless per call]
  └─ for each case → answer_case(resources, llm, case) → CaseResult             [fresh state per case]
        1 input guard      (code)   length cap, control chars, user_id format/known
        2 tripwire         (code)   fraud / hardship / human-only action / human requested → forced escalation (+ fraud mode)
        3 request build    (code)   static prefix (rules + all policies) + case suffix
        4 LLM call #1      (model)  may call get_my_orders once, or answer directly
        5 tool execution   (code)   closure bound to case.user_id; neutral facts
        6 LLM call #2      (model)  final structured answer; tools disabled (mode NONE)
        7 output validator (code)   narrow invariants → ≤1 repair call → else safe failure
        8 route derivation (code)   from escalation signal + actual tool use + citations
        9 trace            (code)   per-case JSONL record
  └─ write answers.jsonl {id, route, answer}; write trace.jsonl
```

Max LLM calls per case: **3** (answer-or-tool, post-tool answer, one repair). Typical: 1 (policy/escalation) or 2 (order questions).

## 2. Module layout (`src/support_agent/`)

| Module | Responsibility | Key requirements |
|---|---|---|
| `config.py` | `Settings` frozen dataclass from env: provider, primary/fallback model, timeout, max attempts, max output tokens, input char cap, data paths | OWN-02, OWN-06, SEC-07, SEC-13 |
| `resources.py` | Load and validate once: `PolicyCorpus` (id `POL-01..12`, title, text; stable ordering), `OrdersRepository` (Pydantic v2 strict models, read-only), `today` from `orders.json` | SEZ-F06, OWN-03, OWN-04 |
| `facts.py` | Neutral derived facts per order (see §4). Pure functions of (order, today). | ADR-1 boundary |
| `tools.py` | `build_toolset(user_id, repo, today)` → registry with one read-only tool `get_my_orders`; JSON schema; `not_found` parity | SEC-01..04 |
| `prompts.py` | System prompt template (rules, voice, output contract) + rendered policy block; `PROMPT_VERSION` = short hash of the static prefix | SEZ-F02, SEC-08 |
| `guards.py` | `InputGuard`, `Tripwire`, `OutputValidator` | SEC-05, SEC-06, SEC-09, SEC-11 |
| `routing.py` | `derive_route(...)` (§6) | SEZ-C04 |
| `agent.py` | `answer_case()` — the loop (§5); returns `CaseResult(route, answer, trace)` | SEZ-F01, OWN-04 |
| `llm/base.py` | `LLMClient` protocol + normalized types + `ProviderError` taxonomy | OWN-02 |
| `llm/gemini.py` | `google-genai` adapter (AFC disabled, timeouts, retry/failover) | OWN-02, OWN-06, SEC-07 |
| `llm/fake.py` | Scripted `FakeLLM` for tests/CI (tool call → answer sequences, injected errors) | OWN-07 |
| `trace.py` | `TraceRecord` dataclass → JSONL | OWN-07 |

`run_cases.py` (repo root) is a thin CLI over `answer_case`. `evals/score.py` scores answers against case files (owned by the evaluation agent; spec in `specs/evaluation.md`).

## 3. Contracts

### 3.1 CLI
`python3 run_cases.py <cases.jsonl> <answers.jsonl> [--trace <trace.jsonl>]` — the optional flag defaults to `<answers>.trace.jsonl`.

**Exit codes:**
- **0:** every input line produced an output line, including safe-failure lines.
- **2:** unusable input/config (missing file, missing `GOOGLE_API_KEY` for provider `gemini`, incompatible model without override). Nothing is written.
- **3:** the auth/billing circuit breaker opened (§7). **All** lines are still written, with safe-failure answers from the breaker point on, plus one stderr diagnostic.

### 3.2 Tool: `get_my_orders`
- **Parameters** (model-supplied, all optional): `order_id: string` (pattern `^ord_\d{1,6}$`; anything else → treated as no match), `merchant: string` (≤ 60 chars; case-insensitive exact/substring match against the caller's merchants).
- **Never** a `user_id` parameter. The closure binds `case.user_id` (SEC-01).
- **Algorithm:** `orders = repo.orders_for(user_id)` **first**, then filter by `order_id`/`merchant` (SEC-02).
- **Result:**
  - `{"status": "ok", "today": "2026-07-01", "orders": [OrderView…]}`, or
  - `{"status": "not_found", "today": "2026-07-01", "orders": []}` — identical payload whether the ID belongs to another user or doesn't exist (SEC-03).
  - No filter → all of the caller's orders.
  - Unknown user → `not_found` with no orders.
- **`OrderView`** = recorded fields (`order_id`, `merchant`, `order_date`, `total`, `plan`, `status`, `reschedules_used`, `refund`, `installments[]`) + `facts` (§4). No other users' data; no names (not needed).

### 3.3 Final answer schema (structured output, both call #1-direct and call #2) — canonical
```json
{
  "answer": "string (<= 1200 chars, plain text)",
  "escalation_reason": "none | dispute | hardship | fraud | decline_or_limit | fee_dispute | credit_report | refund_overdue | human_requested | out_of_policy_action | other",
  "policy_applied": true,
  "cited_policies": ["POL-01", "..."]
}
```
- `escalation_reason` is always a string; `"none"` when not escalating (never null).
- `policy_applied` is **true only when a policy rule was needed to interpret or decide something about the shopper's order data**, beyond reporting recorded values. Reading a due date/amount is `false`; judging whether a reschedule is free is `true`. It is the route signal for tool cases (§6), deliberately separate from citations. [AR-02]
- `cited_policies` = the docs whose rules the answer relies on (used for grounding/eval). Unknown IDs are dropped (validator `warn`). `policy_applied=true` with no valid citation → validator `warn`.

### 3.4 `LLMClient` protocol (normalized, provider-agnostic)
`generate(req: LLMRequest) -> LLMResponse`.
- `LLMRequest`: static system text, case contents (history incl. provider-native model turns), tool declarations or none, tool mode (`auto` | `none`), response schema, max output tokens.
- `LLMResponse`: `function_calls[]`, `final_json | None`, `raw_model_turn` (opaque; appended to history **unchanged** so Gemini 3 thought signatures survive), `usage{input, output, cached, thoughts}`, `model_id`, `latency_ms`, `attempts`.
- Raises `ProviderError(kind=…)` (§7).

## 4. Deterministic facts vs. LLM responsibility (boundary — see ADR-1)

| Responsibility | Owner | Examples |
|---|---|---|
| Interpret the request, decide whether order data is needed, choose tool arguments, pick the applicable policy rules, apply them to the facts, decide escalation, write the reply | **LLM** | "Can I push back my payment?" → look up order, apply POL-02 |
| Authorization, data access scoping, tool boundaries | **Code** | SEC-01..04 |
| **Neutral facts** (arithmetic/selection with no policy thresholds): `today`; `next_upcoming_installment` (lowest-numbered `upcoming`); `days_until_due` for upcoming installments; `unpaid_balance` (sum of non-paid installments); `failed_installments[]`; `paused_installments[]`; `refund.business_days_since_issued` (Mon–Fri, A-07); `days_since_order` | **Code** (`facts.py`) | Removes date/amount arithmetic errors without deciding outcomes |
| **Business invariants** checked on the output (never generating it) | **Code** (`OutputValidator`) | SEC-06 list |
| One-way escalation tripwire (fraud, hardship, explicit human-only action requests, explicit human request) — adds escalation, never answers | **Code** | SEC-09 [AR-07] |
| **Policy-conclusion facts** (e.g. `next_reschedule_fee`, `reschedule_eligible`, `refund_to_payment_method`) | **Not in baseline.** Allowed later only as a measured iteration: a failure observed in an eval run, the fact added, a rerun delta recorded in `ITERATION.md`, and the ADR-1 boundary note updated | Iteration lever |

Rule of thumb: code may compute *what is true about the data*; the model decides *what the policy says to do about it*; code then checks the reply didn't break an invariant.

## 5. The loop (`agent.answer_case`)

1. **Input guard:** truncate to `INPUT_CHAR_CAP` (default 2000), strip control characters, flag if truncated. Validate the `user_id` format; if the user is unknown, the toolset returns `not_found` (no special answer path).
2. **Tripwire** (one-way; it never writes answer text): a conservative, precision-first phrase classifier with generic support vocabulary — *not* derived from golden or adversarial questions. It sets `forced_reason`:
   - `fraud` (unrecognised order, stolen card, account takeover) → also `fraud_mode=True`: the order tool is **not registered** for this case.
   - `hardship` (job loss, can't afford payments, medical emergency, disaster).
   - `human_only_action` [AR-07]: an explicit **request to perform** a human-only action — waive/remove a fee, raise/tell the exact limit or override a decline, correct a credit report, file/update/close a dispute, pause payments. The detector targets imperative/request phrasing ("waive my fee", "remove the charge", "what is my exact limit", "file a dispute for me"), not informational questions ("how do disputes work?").
   - `human_requested` (A-15): the shopper explicitly asks for a human agent.

   Anything the tripwire misses is still the model's job (`escalation_reason`), and is measured by eval as UNDER_ESCALATION.
3. **Request:**
   - System instruction = static prefix (identical bytes across cases → cache-friendly): role and domain scope, rules, voice, output contract, then all 12 policies as `[POL-NN] <title>\n<text>`.
   - Case message = `today`, tripwire note (if any), and the user question wrapped in `<shopper_message>` delimiters marked as untrusted data.
4. **Call #1:**
   - Tools = `[get_my_orders]` unless fraud mode; tool mode `auto`; response schema set. Smoke test confirmed tools + JSON schema combine on 3.x Flash-Lite; 2.5 Flash-Lite rejects the combination.
   - If final JSON is returned → go to step 7.
5. **Tool execution:**
   - Accept **only** the first call to a registered tool name. Ignore any others, and record them in the trace.
   - Validate arguments (schema + pattern), execute the closure, and append `raw_model_turn` + the function response.
6. **Call #2:** tool mode `none` — the model structurally cannot call again — with the response schema set.
7. **Validation:**
   - Parse into the Pydantic `FinalAnswer`, then run the `OutputValidator` (`specs/security.md` §4).
   - On violation: **one** repair call (tool mode `none`) with a short machine-generated list of the violations.
   - Still invalid → safe failure (SEC-10).
8. **Route:** derived as in §6.
9. **Result + trace:** return `CaseResult` and `TraceRecord`.

## 6. Route derivation (`routing.derive_route`)
```
if forced_reason or final.escalation_reason != "none":  route = "escalate"
elif tool_executed:                                     route = "both" if final.policy_applied else "tool"
else:                                                   route = "policy"   # incl. out-of-scope decline (A-09)
```
- `tool_executed` = the tool actually ran, including a `not_found` result (A-08).
- The model never writes `route`. [AR-02]
- **Why `policy_applied` rather than citations** (review R-00 #5): the smoke test showed the same synthetic question labelled `tool` and `both` across runs, and citations are naturally emitted even on pure lookups. A dedicated boolean with a precise definition (§3.3) separates "I reported your data" from "I applied a rule to your data".
- **Residual risk:** the model can still mis-set the flag. This is measured by ROUTE_MISS in eval, and prompt-level definition changes are logged in `ITERATION.md`. No per-case hacks.
- **Unit tests:** cover all four routes, plus the precedence of `forced_reason` over the model's fields.
- **Validation basis (P-005 §4):** the rule encodes the official route semantics: "answers what it can" → `policy`, "looks up what it must" → `tool`/`both`, "escalates what it shouldn't touch" → `escalate` (PROMPT.md "The problem"), plus the policy-mandated escalations (SEZ-P*). It contains no case-specific logic. Evidence is taken across golden, adversarial_dev and the unseen holdout, never golden alone.

## 7. Provider errors, retry, fallback (`llm/gemini.py`)

**Terminology.** A case makes ≤ 3 **semantic calls** (`initial`, `post_tool`, `repair`). Each semantic call makes ≤ `LLM_MAX_ATTEMPTS` (default 2) **transport attempts** in total across the primary and fallback models.

| Condition | `error_class` | Same-model retry? | Fallback-eligible? | Case outcome |
|---|---|---|---|---|
| 429 per-minute limit | `rate_limit_minute` | yes, 1× after short jittered backoff (≤ 1 s) | yes | normal if recovered |
| 429 daily quota (per-day quota id/message) | `quota_daily` | no | yes; circuit-break that model for the rest of the batch | normal if fallback works |
| 500/502/503/504 | `server_5xx` | yes, 1× | yes | normal if recovered |
| Client timeout | `timeout` | yes, only if the case deadline allows | yes | normal if recovered |
| 404 model not found | `model_not_found` | no | yes | normal if fallback works; config warning |
| 400 invalid argument / schema | `bad_request` | no | no (bug) | SEC-10 safe failure |
| Invalid key (400/401), 403 permission/billing, FAILED_PRECONDITION | `auth_billing` | no | no | **Circuit breaker:** this and every remaining case get the SEC-10 line with no further calls; one stderr diagnostic; exit code 3 |
| Finish reason SAFETY / PROHIBITED | `blocked_safety` | no | no | SEC-10 |
| Malformed function call / unparseable JSON | `malformed_output` | → repair semantic call (step 7) | — | SEC-10 if repair fails (`validation_exhausted`) |
| `MAX_LLM_CALLS_PER_BATCH` reached | `batch_limit` | — | — | SEC-10 for remaining cases |

- **Settings:** `LLM_TIMEOUT_S` (default 10 s per attempt, the API minimum), `CASE_DEADLINE_S` (default 30 s per case), `LLM_MAX_ATTEMPTS=2`.
- **Consequence for ADR-3:** a client can't enforce a per-request deadline below 10 s on this API, so a p95 ≤ 3 s target has to come from low typical latency plus a production-side cutoff (e.g. an async cancel at the service layer), not from the SDK timeout.
- **`PROMPT_VERSION`** = sha256 of (static system prefix + tool declarations + final-answer schema). `corpus_hash` = sha256 of the policy files concatenated in POL order. Both go in every trace line and in the run `config.json`.
- The SDK's built-in retries stay **off** (its defaults of 5 attempts and a 60 s max delay conflict with SEC-07); our loop owns retries.
- The fallback model must support tools + JSON schema together, i.e. **3.x Flash-Lite** (smoke test S-001).
- Failover changes the **model only**, never the credential or project. There is no automatic switch to another project/key with different data-handling terms (OD-16).

## 8. Configuration (env; `.env` via `uv run --env-file .env`)

| Var | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `gemini` | `gemini` \| `fake` |
| `GEMINI_PRIMARY_MODEL` | `gemini-3.5-flash-lite` (owner decision OD-15) | Configurable; explicit pinned ID, no `-latest` alias |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.1-flash-lite` (OD-15); empty = disabled | Must be compatible: tools + JSON response schema in one call. The config accepts a known-compatible set (`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, verified by S-001); any other ID needs `--allow-unverified-model`, and a `live` compatibility test re-verifies. Equal to primary → ignored with a warning. The fallback uses the **same credential/project** (OD-16) |
| `FAKE_LLM_SCRIPT` | empty | provider = `fake` only. Path to a JSON script of responses; if empty, the **default fake responder** returns one direct final answer per case: `{"answer": "[fake] offline answer", "escalation_reason": "none", "policy_applied": false, "cited_policies": []}`, which makes the CLI runnable offline (route `policy`, or `escalate` + safe failure when the tripwire fires, since the fake answer has no hand-off) |
| `GOOGLE_API_KEY` | — (required for `gemini`; exit 2 if missing) | **The only key source** [AR-09]. The adapter passes it explicitly to `genai.Client(api_key=…)` and never lets the SDK read `GEMINI_API_KEY`/`GOOGLE_API_KEY` from the inherited environment on its own. An inherited `GEMINI_API_KEY` (e.g. from tmux) is ignored. Run `config.json` records `credential_env_var` + `credential_fingerprint` (12-hex SHA-256 prefix), never the value |
| `GEMINI_THINKING_LEVEL` | `minimal` | smoke test: no thought tokens billed at `minimal` |
| `LLM_TIMEOUT_S` / `LLM_MAX_ATTEMPTS` | `10` / `2` | The Gemini API rejects per-request deadlines below 10 s ("Minimum allowed deadline is 10s", observed in the live smoke call on 2026-09-28). Lower values are raised to 10 s with a warning |
| `CASE_DEADLINE_S` | `30` | One absolute deadline per case, shared by all semantic calls and attempts (R-01 #4). No new attempt starts if less than 10 s remains; exhausted → SEC-10 with `timeout` |
| `LLM_MAX_OUTPUT_TOKENS` | `600` | |
| `INPUT_CHAR_CAP` | `2000` | |
| `MAX_LLM_CALLS_PER_BATCH` | `2000` | batch-level consumption guard; exceeding it → safe failure for the remaining cases |
| `DATA_DIR` | `data` | policies + orders location |

## 9. Concurrency path (not built now)
- `answer_case` is a pure function of `(Resources, LLMClient, Case)`, and `Resources` is immutable.
- Bounded concurrency later = `ThreadPoolExecutor(max_workers=N)` or `asyncio` + `Semaphore(N)` around the same function, with output order restored by index.
- Client sharing: the thread-safety of `google-genai` is undocumented (stack report). If unverified, use one client per worker.
- Nothing else changes.

## 10. Observability
- One `TraceRecord` per case. Schema in `specs/evaluation.md`: model, attempts, tool calls, tripwire, validator verdicts, route inputs, tokens incl. cached, latency, error class.
- Traces never contain keys, headers or raw request objects.
- `evals/score.py` aggregates them into p50/p95 latency, tokens and $/question.
