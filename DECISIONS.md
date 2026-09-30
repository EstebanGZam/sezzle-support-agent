# Decision Records

Exactly three records, in the format the brief requires: *decision · options considered · why · what evidence would change my mind*. Every number comes from committed runs in `evals/runs/` (see `ITERATION.md`); estimates are labelled as such. Supplementary decisions, including the owner's provider change (OD-26), are in `docs/decision-log.md`.

## ADR-1 — Guardrails live in code; the model interprets and answers
- **Decision:** the LLM reads each request, decides whether to call the single read-only `get_my_orders` tool, applies the policies and writes every answer. Code owns identity (`user_id` is closure-bound, never a tool argument) and caller-scoped data (the same `not_found` for foreign and missing IDs). It also computes neutral facts (dates, balances, business days) and runs a one-way escalation tripwire for fraud, hardship and explicit human-only requests. A typed-claim output validator checks foreign IDs, order figures, action claims, waiver/limit promises and hand-off coherence; a failure gets one repair call, then a safe escalation.
- **Options:** (a) prompt-only rules; (b) code decides eligibility and fees, and the LLM only paraphrases; (c) **the model decides, code constrains and checks**.
- **Why (c):** (a) fails under injection, and (b) turns the LLM into a formatter, which the brief rejects. Under (c), data leakage and write actions are structurally impossible. Across 105 real case executions (runs 003–005) there were **0 UNSAFE_PROMISE and 0 confirmed AUTHZ_LEAK**; the one automatic AUTHZ_LEAK flag was a false positive, a not-found reply echoing the ID the shopper typed. Policy misapplication is measured, not blocked, and it is the dominant failure (GROUNDING_MISS, ROUTE_MISS).
- **Would change my mind:** a policy-application error that keeps recurring on the same rule after prompt iteration (e.g. refund application, v10, missed in runs 003–005) → move that single fact into code. Separately, 2/35 (run 004) and 3/25 (run 005 dev) cases ended in `validation_exhausted`; if manual review shows those answers were correct → narrow the checks.

## ADR-2 — Full policy corpus in context, no retrieval layer
- **Decision:** all 12 policies (~2.2k tokens) sit in a static, byte-identical system prefix with `[POL-NN]` IDs. The model reports `cited_policies`, and code validates them.
- **Options:** full context; BM25/keyword top-k; embeddings + vector store; a policy-lookup tool.
- **Why:**
  - The corpus is tiny, so retrieval can only add recall misses ("push back my payment" vs "reschedule"), latency and moving parts.
  - The one-call path averaged **1.48 calls/case** on Groq (run 004). A lookup tool would add a call.
  - On the Groq path the fixed prefix produced **35.8 % cached input tokens** in run 004.
- **Would change my mind:** the prefix dominates cost. Measured on Gemini (run 003, 14 valid cases): **5.2k input tokens/case with 0 cached tokens** — the ~3.3k-token prefix is below the documented 4,096-token implicit-cache minimum. If explicit caching isn't available, **BM25 over policy sections is the next trade** (it roughly halves input). It would be judged on the same GROUNDING_MISS/ROUTE_MISS labels.

## ADR-3 — Cost/latency at 100k questions/day, $50/day, p95 ≤ 3 s
- **Decision:** a small model (Flash-Lite class) with minimal/low reasoning and at most 1 tool round (policy and escalation questions take 1 call, order questions 2). Output is capped. On overload it fails over to a second model, with a batch-level primary-health cooldown, and it escalates safely instead of retrying at length.
- **Options:** a larger model; always 2 calls; prefetching the caller's orders into one call; prefix caching; a smaller prefix via retrieval.
- **Why:** the budget is $50 / 100k = **$0.0005/question**; only a small model with mostly single-call answers can approach it. **Measured:** Gemini 3.1 / 3.5 Flash-Lite list prices × run-003 tokens = **$0.0015 / $0.0018 per question uncached, ≈3× over budget**. Groq gpt-oss-120b (run 004) service latency per case was **p50 1.16 s, p95 4.1 s** (per attempt p50 0.84 s, p95 1.3 s); p95 misses 3 s only on 3-call (repair) cases.
- **What I'd trade, in order:** (1) get the prefix cached, via an explicit cache or padding past the minimum (≈5–6× cheaper input; ≈ $0.0006/question estimated at 3.1 Flash-Lite prices from the measured tokens); (2) shrink the prefix with retrieval (ADR-2); (3) cut repair calls, which drive the p95 tail; (4) prefetch a minimal order summary so order questions take one call; (5) on timeout, escalate rather than retry.
- **Would change my mind:** a measured cache-hit rate above 80 % on the production provider, or a small model that holds quality without the repair path. An availability incident like runs 001–003 (provider-wide 503s left 21–30 of 35 cases in safe failure) instead argues for a second provider with separate capacity over a cheaper single model.
