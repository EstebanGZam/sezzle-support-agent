# Technology Stack & Architecture Decision Matrix — FOR OWNER REVIEW

- Date: 2026-09-27 · Status: **PROPOSED — nothing here is approved or locked.** The owner (user) decides.
- Inputs: the assessment package (PROMPT.md, SUBMISSION.md, 12 policies, DATA-orders.json, golden cases), `ADVISORY_REPORT.md`, and `research/*` — including two new inputs: `research/stack-report.md` (fact check, Claude) and `research/architecture-challenge-review.md` (independent skeptical review, Codex).
- Tags: **[REQ]** explicit Sezzle requirement (quoted source) · **[OWNER]** requirement from the owner's own brief (not Sezzle) · **[REC]** our recommendation · **[ASM]** assumption · **[V]/[U]** externally verified / unverified.
- Effort = estimated minutes inside the ~120-min timed build (**[ASM]** — estimates, not measurements).

---

## 0. Requirements that constrain every decision (verbatim sources)

| ID | Requirement | Source |
|---|---|---|
| R-LLM | "A solution with no working LLM in the pipeline does not meet the brief … Deterministic logic *around* the model (pre-filters, authorization, output validation) is welcome … deterministic routing-and-answering *instead of* the model is not." | [REQ] PROMPT.md §"The LLM is the assignment" |
| R-CLI | "include a `run_cases.py` that reads a JSONL of `{id, question, user_id}` and writes `answers.jsonl` of `{id, route, answer}`: `python3 run_cases.py <cases.jsonl> <answers.jsonl>`" | [REQ] PROMPT.md §"The one contract" |
| R-HOSTILE | Eng II: "guardrails that survive hostile input (order IDs that aren't yours or don't exist, fee-waiver demands, instructions to ignore its rules)" | [REQ] PROMPT.md §"Level expectations" |
| R-STRUCT | Graded: "what the model is *structurally* prevented from doing vs. merely told not to" | [REQ] PROMPT.md §"What we grade" #3 |
| R-SCALE | "100k questions/day, an inference budget of ~$50/day, p95 latency ≤ 3 seconds" — answered in an ADR, not built | [REQ] PROMPT.md §"Design constraint" |
| R-NOTGRADED | "We do **not** grade scaffolding quality, provider choice, or lines of code." | [REQ] PROMPT.md |
| R-PRIVATE | "Please don't post the challenge or your solution publicly." Zip or private repo shared with reviewer. | [REQ] SUBMISSION.md |
| R-TIME | "~2 hours … stop at the budget" | [REQ] PROMPT.md |
| O-FALLBACK | "The application must also support an economical fallback if paid access becomes unavailable." | [OWNER] master prompt §10 — **not** a Sezzle requirement |
| O-DEMO | "should ideally remain accessible for approximately 2–3 weeks" | [OWNER] master prompt §14 — "ideally"; Sezzle does not require deployment |

---

## 1. Summary matrix (one row per decision)

| # | Decision | Options | Recommended [REC] | Effort | Pick another option when… |
|---|---|---|---|---|---|
| D1 | Repo layout & assessment materials | (a) keep flat originals · (b) copy into the documented `data/`/`cases/` layout + provenance manifest · (c) exclude materials (sanitized repo) | **(b)** | 5 min | (c) if the HM says materials must not leave your machine; (a) if you want zero transformation |
| D2 | Language / framework | Python CLI · Python + FastAPI · Spring Boot · TypeScript | **Python 3.12 CLI (no web framework)** | 0 | FastAPI only if you approve a demo (D10); Java/TS only if the HM waives `python3 run_cases.py` |
| D3 | LLM orchestration | raw `google-genai` + own loop · Pydantic AI · LiteLLM · LangGraph · OpenAI-compatible endpoint | **raw `google-genai` + own ≤1-tool-round loop + thin `LLMClient` protocol** | 25–35 min | Pydantic AI if a 2nd provider becomes mandatory (HM answer) |
| D4 | Policy grounding | full-context · BM25/keyword top-k · embeddings/vector · policy-lookup tool | **full-context, stable prefix, doc IDs + validated citations** | 5 min | BM25 top-k if measured cost > budget (see D4 ADR note) |
| D5 | Shared resources / concurrency / sessions | sequential stateless per case · bounded async concurrency · session framework | **load-once immutable resources; fresh per-case state; sequential** | 5 min | bounded `asyncio.Semaphore` if the hidden set is large/slow |
| D6 | Validation, authz, app security | prompt-only · structural controls (closure-bound tool, not-found parity, schema, narrow validator, tripwire) · global numeric firewall | **structural controls with a *narrow* validator** | 25–30 min | global numeric validator only if eval shows invented numbers the narrow one misses |
| D7 | Gemini config & portability | single model · primary+fallback model · +free-tier key · +2nd provider | **single pinned model + config-only fallback model with 1 failover; no free tier** | 10 min | 2nd provider adapter if the HM will run with non-Gemini keys |
| D8 | Tests, eval, observability | pytest+fake LLM · eval harness + JSONL traces · hosted tracing (Langfuse/OTel) | **pytest+FakeLLM, regex/route scorer, local JSONL traces** | 20 min (parallel) | hosted tracing never here (external data egress, setup) |
| D9 | Deps, CI, deploy | uv+lock (+exported requirements.txt) · pip only · Poetry; CI yes/no; deploy none/Cloud Run/Render | **uv + `uv.lock` + exported `requirements.txt`; CI only if GitHub repo; no deploy** | 5–10 min | Cloud Run gated demo if you insist on O-DEMO |
| D10 | Dev-tool integration | single agent · lead + 1 implementer + parallel eval + cross-provider reviewer · parallel implementers · Claude Cloud | **lead + 1 implementer (worktree) + eval-harness mate + Codex reviewer; Cloud optional** | overhead ~5 min | single-agent if quotas are tight at build time |

The sections below give the evidence for each row.

---

## D1 — Repository structure & original assessment materials

**Relevant:** R-CLI (reviewers run your script on a hidden set "in the same format"); PROMPT.md names `data/policies/`, `data/orders.json`, `cases/golden_visible.jsonl`, but the package is flat (`POLICY_-_01-…`, `DATA-orders.json`, `CASES_-_golden_visible.jsonl`) [V]; R-PRIVATE (private repo explicitly allowed); owner rule "do not modify the original assessment files".

| Option | Pros | Cons |
|---|---|---|
| (a) Flat originals at repo root | Zero transformation | Mismatches the paths PROMPT.md documents; clutters the root; odd names (`_-_01` vs `_-02`) |
| **(b) Copy to documented layout + `assessment/MANIFEST.md`** (original name → repo path → sha256), `PROMPT.md`/`SUBMISSION.md` kept verbatim under `assessment/` | Matches what reviewers expect; provenance is auditable; originals untouched outside the repo | Renaming must be recorded (manifest handles it) |
| (c) Exclude materials; load from an external path | Maximum confidentiality | Reviewer can't run it without re-assembling files; adds friction; SUBMISSION.md already allows a private repo |

**Proposed tree [REC]:**

```
assessment/{PROMPT.md, SUBMISSION.md, MANIFEST.md}
data/policies/01-payment-schedules.md … 12-supported-merchants-limits.md
data/orders.json
cases/{golden_visible.jsonl, adversarial_dev.jsonl, adversarial_holdout.jsonl}
src/support_agent/…
tests/
evals/{score.py, runs/<NNN>_<label>/}
specs/{requirements.md, tasks.md}
run_cases.py
README.md  DECISIONS.md  PROMPTS.md  ITERATION.md  AGENTS.md  CLAUDE.md
pyproject.toml  uv.lock  requirements.txt  .env.example  .gitignore  [.github/workflows/ci.yml]
```

- **Security:** the materials are synthetic (SUBMISSION.md) and a private repo is allowed. `.env` is git-ignored before the first commit.
- **Paths:** loaded from a config default, so a reviewer can point to other files.

---

## D2 — Application language & framework

**Relevant:** R-CLI makes `python3 run_cases.py` a hard entry point [REQ]; R-NOTGRADED; R-TIME.

| Option | Pros | Cons | Effort vs Python |
|---|---|---|---|
| **Python 3.12, plain CLI** (argparse) | Satisfies R-CLI natively; first-class Gemini SDK [V: google-genai 2.25, Py ≥3.10]; Pydantic; fastest to iterate | No web surface (not required) | baseline |
| Python + FastAPI | Ready for a demo/API; async | Adds a surface nobody grades; needs async client and lifecycle management | +15–20 min |
| Spring Boot + Spring AI 2.0.1 | Spring AI supports Gemini tool calling + structured output [V: docs.spring.io google-genai-chat]; strong typing | Still needs a Python shim for R-CLI; Gemini 3 thought-signature handling unverified [U]; JVM build overhead | +30–45 min [ASM] |
| TypeScript (Vercel AI SDK etc.) | Good tool-calling ergonomics | Same R-CLI shim problem; no advantage here | +20–30 min [ASM] |

- **[REC]** Python 3.12. It has the broadest wheel support, and 3.13 also works [U, judgment].
- **Python 3.13:** only if your machine standard is 3.13 (it currently has 3.13.13).
- **FastAPI:** only if D9 approves a demo, and then as a thin adapter over the same `answer(question, user_id)` core.

---

## D3 — LLM orchestration & tool calling

**Relevant:** R-LLM, R-STRUCT, R-HOSTILE, R-SCALE (p95 ≤ 3 s), golden v01/v03/v04/v10 require an order lookup.

| Option | Pros | Cons | Security / maintainability |
|---|---|---|---|
| **Raw `google-genai`, AFC disabled, own loop** | Every tool call is visible, authorized and capped in *your* code, which is exactly what R-STRUCT grades; supports tool calling + structured output together on Gemini 3 [V]; `VALIDATED` mode for tool args [V] | You hand-write ~60 lines of loop + a fake client | Best auditability; pin `google-genai>=2.25,<3` (AFC behaviour changes in 3.0 [V]) |
| Pydantic AI 2.51 (stable) [V] | Provider-swappable, `FallbackModel`, `TestModel`/`FunctionModel` for offline tests [V] | Framework concepts spread through the code; 20–30 min learning cost [ASM]; hides the loop you want to show | Good, but adds indirection |
| LiteLLM | Wide provider coverage; handles Gemini thought signatures [V] | Heavy dependencies; translation layer lags new Gemini features [U] | More supply-chain surface |
| LangGraph / LangChain | Graphs, memory | Over-engineering for 1 tool and single-turn; obscures decisions | Not justified |
| Gemini OpenAI-compatible endpoint | One `openai` code path for several providers | **Beta**; parameters can be dropped without error; caching and thinking need Gemini `extra_body`, so the code isn't really portable [V: ai.google.dev/gemini-api/docs/openai] | Silent drops are a correctness risk |

**Loop shape [REC], revised after the independent review:**
- At most **1 tool call** followed by 1 continuation. Policy-only and escalation questions finish in 1 inference; account questions take 2.
- The advisory report's "≤2 rounds" was cut: it adds latency and branches without a case that needs it.
- A **single-call prefetch** (the caller's minimal order summary placed in the prompt) stays as an *ADR alternative* and as the time-box fallback. It is not the primary design, because it weakens data minimization and makes `tool` vs `policy` unobservable.

**Tool surface [REC]:**
- One read-only tool, `get_my_orders(order_id?: str, merchant?: str)`, bound to the case's `user_id` by closure.
- It returns all matches for the caller; foreign and nonexistent IDs return an identical `not_found`.

**Derived facts: the review challenged this and it's your call (see D6).** Two positions:
- **(i) Neutral facts only [REC now]:** frozen `today`, installments sorted, next *upcoming* installment, days until due, business days since refund issued. The model combines these with policy.
- **(ii) Policy conclusions in code:** `reschedule_eligible`, `next_fee`, `failed ⇒ repay`, `refund_disposition`. More reliable answers, but the review argues it crosses R-LLM: code, not the model, would be answering v03/v04/v10.

---

## D4 — Policy grounding

**Relevant:** corpus = 12 docs ≈ 8.5 KB ≈ 2.2k tokens [V, measured locally]; R-STRUCT; R-SCALE; golden v02/v08 policy-only, v06 escalate + policy.

| Option | Pros | Cons | Effort |
|---|---|---|---|
| **Full-context injection, stable prefix, `[POL-01]…` IDs, model returns `cited_policies[]`, code validates IDs** | No recall misses; simplest; cite-able; the prefix is identical across all cases | Pays ~2.2k input tokens on every call | 5 min |
| BM25/keyword top-k (e.g. `rank-bm25`) | Smaller prompt (~1.5k tokens) → cheaper at scale | Recall misses on paraphrases ("push back my payment" vs "reschedule"); one more dependency | +15 min |
| Embeddings + vector store | Semantic recall | Unjustified for 12 docs; index management; extra API calls and latency | +30–45 min |
| Policy-lookup tool (`get_policy(id)`) | "Policy used" becomes observable in the trace | Extra round trip hurts p95; the model may skip it | +10 min |

**The ADR point you'll need, from new evidence:**
- A ~3.3k-token shared prefix is **below the documented 4,096-token implicit-cache minimum** for 3.x Flash models. The Flash-Lite minimum is **undocumented** [V gap: ai.google.dev caching docs; research/stack-report.md §4].
- At 100k questions/day on `gemini-3.1-flash-lite`, the prefix costs ≈ **$82/day uncached vs ≈ $8/day cached**, input only (derived arithmetic).
- **The $50/day budget therefore hinges on caching or on shrinking the prefix.** The first real eval run should log `usage_metadata.cached_content_token_count` so the ADR is measured, not asserted.
- **Options to put in the ADR:**
  - Explicit `caches.create` for the policy prefix (1 h default TTL [V], storage ≈ $0.08/day).
  - Pad the prefix above the minimum with few-shot examples.
  - BM25 to shrink the prefix.

---

## D5 — Shared knowledge resources, concurrency, independent sessions

**Relevant:** R-CLI is batch and single-turn, with no conversation state in the contract [V]; R-HOSTILE (no cross-user leakage); R-SCALE (production story).

| Option | Pros | Cons |
|---|---|---|
| **Load once, immutable; fresh per-case state; sequential** | Policies and orders are parsed once into frozen Pydantic models / read-only mappings. Each case gets new messages, a new trace and a new tool closure bound to *its* `user_id`, so nothing can carry over between users. Deterministic ordering; friendly to rate limits | Slower for large hidden sets (~1–2 s per case [ASM]) |
| Bounded async concurrency (`client.aio` + `asyncio.Semaphore(N)`) | Faster batch; same isolation model | Needs async plumbing; ~10 min; rate-limit interplay |
| Session / conversation framework | Multi-turn memory | Not in the contract; adds a leakage risk; unjustified |

- **Production story (ADR text, not built):** stateless request handlers share the immutable corpus and one explicit-cache handle; the model client is a single instance created at startup and closed on shutdown (thread safety undocumented → treated as an assumption [U]); per-user state lives nowhere but the request.
- **Test [REC]:** run u001 then u002 in one process and assert that no u001 order ID appears in u002's trace.

---

## D6 — Data validation, authorization, application-level security

**Relevant:** R-HOSTILE, R-STRUCT, R-LLM; policies 03/05/07/09/11/12 (human-only actions); OWASP LLM01/02/05/06/07/09/10 mapping in `research/security-report.md`.

| Control | Type | Recommend? | Why / trade-off |
|---|---|---|---|
| Pydantic v2 strict models for `orders.json` (status `Literal`s, `date`, `Decimal`) loaded once | structural | **Yes** | Fail fast on bad data; typed tool results [V: pydantic JSON docs] |
| `user_id` only from the harness, never a tool parameter; tool filters by it *before* matching | structural | **Yes** | Core IDOR defence (v-cases on foreign IDs) |
| Identical `not_found` for foreign and nonexistent IDs | structural | **Yes** | No existence oracle |
| Unknown `user_id` → no tool data, graceful answer | structural | **Yes** | Hidden set may use unseen IDs [ASM] |
| Read-only tool surface (no reschedule/waive/pause functions exist) | structural | **Yes** | The model *cannot* act (LLM06) |
| Structured output: `route` enum, `escalation_reason` enum, `cited_policies` ⊆ known IDs | structural | **Yes** | Contract safety (C-04) |
| **Route derivation: hybrid** — escalation reason or tripwire ⇒ `escalate`; else tool actually called + policy cited ⇒ `both`; tool only ⇒ `tool`; citations only ⇒ `policy` | structural | **Yes (revised)** | Matches all 10 golden labels per the review (v06 = escalate despite explaining policy); the label reflects what happened, not what the model claims |
| Fraud/hardship tripwire (one-way: can only *add* escalation, never answers) | structural | **Yes, narrow** | Protects v07/v09; the model still writes the reply, so R-LLM is respected. Must not grow into a regex router |
| **Narrow output validator:** no foreign `ord_` IDs; no order-specific $/date absent from *this case's tool result* (after canonicalizing currency and dates); no past-tense action claims (`I've (paused\|waived\|rescheduled\|opened)`); no "your limit is"; 1 repair retry → system-failure escalation | structural | **Yes (revised)** | A global "every number must be grounded" check falsely rejects "25%", "two weeks", "2FA", "3–10 business days", and still accepts a wrong `$10` that happens to appear in a policy (review §6) |
| Canary token in the system prompt | structural | Optional (cut first) | Low value: the prompt holds no secrets |
| Input cap (~2k chars), `max_output_tokens`, 1 tool round, timeout | structural | **Yes** | LLM10 unbounded consumption |
| Domain restriction (off-topic → brief polite decline, `policy` route) | prompt + structural (no tools beyond orders, low max tokens) | **Yes** | Customer-support purpose only |
| User text delimited as untrusted; policies only from the corpus loader | prompt + structural | **Yes** | LLM01; injected "policy" text can never become policy |
| Fail-closed template **only** for provider/validation failure | structural | **Yes** | The review warns: if it answers v05–v09 routinely, code is answering (R-LLM) |

**Decision needed:** D3 derived facts, (i) vs (ii). The **[REC]** is (i) neutral facts only, with (ii) as an *iteration lever*: if baseline eval shows date/fee reasoning errors, adding a specific derived fact is a measured, documented change. That makes a good iteration story.

---

## D7 — Gemini integration, configuration, provider portability

**Relevant:** R-NOTGRADED (provider choice); O-FALLBACK (owner); reviewers will run the hidden set with *their* key — provider unknown [OQ]; Gemini Unpaid terms: "Do not submit sensitive, confidential…" [V: ai.google.dev/gemini-api/terms].

| Option | Pros | Cons | Effort |
|---|---|---|---|
| **Single pinned model** (`gemini-3.5-flash-lite` or `gemini-3.1-flash-lite`, [V] both GA and listed by `models.list`) | Simplest, reproducible | No resilience | 0 |
| **+ config-only fallback model, 1 failover on 429/5xx/timeout; auth/billing errors fail fast → system-failure escalation** | Satisfies O-FALLBACK cheaply; separate per-model quota | One more code branch | +10 min |
| + free-tier key failover | "Economical" | Unpaid terms (human review, training); quotas unpublished; silent tier switching is a data-handling risk | +10 min — **not recommended** |
| + 2nd provider adapter (Anthropic/OpenAI) behind the same `LLMClient` protocol | Reviewer can run with their own key | +15–20 min; second prompt/tool-schema dialect to test | only if the HM says so |

- **Config [REC]:** plain env vars read into a frozen dataclass; `.env` loaded with `uv run --env-file .env` [V, local `uv` help], so there's no python-dotenv or pydantic-settings dependency.

```
LLM_PROVIDER=gemini|fake
GEMINI_PRIMARY_MODEL=…   GEMINI_FALLBACK_MODEL=…(optional)
GOOGLE_API_KEY=…         # SDK prefers GOOGLE_API_KEY over GEMINI_API_KEY [V]
LLM_TIMEOUT_S=…          LLM_MAX_ATTEMPTS=2
```

- **Model choice is yours:**
  - `3.5-flash-lite`: newer; Google recommends it for new projects [V]; $0.30/$2.50.
  - `3.1-flash-lite`: cheaper at $0.25/$1.50, with cache pricing clearly listed [V].
  - **[REC]** Decide after one smoke call each *before* the clock (≈ $0.01), or pick 3.1 for the cost ADR's clarity.

---

## D8 — Automated testing, LLM evaluation, observability

**Relevant:** grading #2, the iteration loop ("first … and final run … what the first run got wrong, what you changed, and why") [REQ]; Senior: failure *taxonomy* [REQ].

| Layer | Recommend [REC] | Alternative / when |
|---|---|---|
| Unit tests | `pytest` with `FakeLLM` (scripted tool calls + final JSON): tool scoping, not-found parity, route derivation, validator, cross-case isolation, provider error mapping (429/5xx/timeout injected) | Pydantic AI `TestModel` if D3 picks Pydantic AI |
| LLM eval | `evals/score.py`: `must_include`/`must_not_include` with `re.I` [ASM on grader flags], exact route match, per-category summary, failure taxonomy tags; sets = golden + adversarial_dev + **untouched** adversarial_holdout | LLM-as-judge: not worth it (cost, non-determinism) |
| Run artifacts | `evals/runs/001_baseline/`, …, `NNN_final/` = answers.jsonl + trace.jsonl + score.md, committed unedited | — |
| Observability | per-case JSONL trace: model, attempts, tool calls, validator verdicts, input/output/**cached** tokens, latency ms → p50/p95 and $ per question in score.md | Langfuse/OTel/Logfire: production option only (sends data to a third party; setup) |
| Lint/format | `ruff check` + `ruff format` | — |

- **Effort:** ~20 min, and it can run in parallel with the core build (disjoint files: `evals/`).

---

## D9 — Dependency management, CI, deployment

| Decision | Options | [REC] | Notes |
|---|---|---|---|
| Deps | uv + `pyproject.toml` + `uv.lock` · pip + `requirements.txt` · Poetry | **uv + lock, plus `uv export > requirements.txt`** | Reviewers typing `python3 run_cases.py` may not use uv; ship both. ~4 runtime deps: `google-genai`, `pydantic` (+ dev: `pytest`, `ruff`) |
| CI | none · GitHub Actions (gitleaks → ruff → pytest, `LLM_PROVIDER=fake`) | **Only if D1 uses a GitHub repo** | Free tier: 2,000 min/month on private repos [V]; no branch protection on Free private repos [V] → the gate is local review + CI |
| Deploy | none · Cloud Run (gated, max-instances=1, in-app cap) · Render Free | **None** | Not required by Sezzle; public URL conflicts with R-PRIVATE; if O-DEMO wins: Cloud Run, ≈$4–8 expected, ≤$12 bounded over 21 days (`research/deploy-report.md`) |
| Docker | yes/no | **No** (only if Cloud Run) | No reproducibility gain over `uv.lock` for a CLI |

---

## D10 — Integration with Orchestrator, Claude Code, Codex, tools

**Evidence:** Orchestrator 0.5.4 dispatches headless teammates in worktrees [V, local]; it **cannot launch or track Claude Cloud sessions** [V, source has no cloud refs]; **Codex refuses to run outside a git repo ("Not inside a trusted directory")** [V, observed today, fixed with `git init`], so implementation must happen in a git repo/worktree.

| Option | Pros | Cons |
|---|---|---|
| **Lead (me) + 1 implementer (Claude, worktree) + eval-harness mate (disjoint `evals/`) + Codex reviewer (read-only)** | Implementer ≠ reviewer; parallelism only where files don't overlap; prompts logged | ~5 min coordination overhead |
| Single agent | Lowest overhead | No independent review; weaker "how you directed AI" story |
| Parallel implementers | — | The core is ~400–600 coupled lines; merge conflicts |
| Claude Cloud tasks | Uses the promo credits (unverified: ~$100, expiring Nov 4) | Needs GitHub push plus a broad-permission GitHub App; not scriptable from Orchestrator; setup eats timed minutes |

- **Tooling [REC]:** add only the official Gemini Docs MCP (read-only [V]). Disable non-dev connectors for the build session: several new ones appeared after the account switch (Slack, Miro, Shopify, Tally, Eraser, Atlassian…), which is more context and more data-egress surface.
- **Prompt log:** every dispatch's `task.md` is copied into `PROMPTS.md` records, as done during this advisory phase.

---

## 2. Changes vs. the advisory report (driven by the independent review) — all [REC], pending your approval

1. Tool loop capped at **1** tool round (was ≤2).
2. Derived facts limited to **neutral arithmetic**; policy conclusions become an iteration lever, not the baseline.
3. **Hybrid, code-derived route label** (was: model-declared with reconciliation).
4. **Narrow validator** (was: global numbers/dates ⊆ grounded set).
5. Canary and free-tier failover dropped; fallback model kept as config-only, because it is your requirement (O-FALLBACK), not Sezzle's.
6. Cost ADR must address **the cache minimum gap**, since the 3.3k prefix may not cache.

## 3. Assumptions still open

- **Reviewer environment:** provider/key unknown. This is the biggest portability unknown → HM question.
- **Grader matching:** regexes applied case-insensitively; route scored as exact match.
- **Flash-Lite cache minimum:** undocumented.
- **Client thread-safety:** not documented.
- **Effort estimates:** judgment, not measurement.
- **`reschedules_used`:** order-level is authoritative; `failed` with a future due date = retry pending (per data, not "corrected").
