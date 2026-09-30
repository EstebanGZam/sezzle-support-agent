# Decision Records

Exactly three records, in the format the brief requires: *decision · options considered · why · what evidence would change my mind*. Every number comes from committed runs in `evals/runs/` (see `ITERATION.md`); estimates are labelled as such. Supplementary decisions, including the owner's provider change (OD-26), are in `docs/decision-log.md`.

## ADR-1 — Guardrails live in code; the model interprets and answers
- **Decision:**
  - The LLM reads each request, decides whether to call the single read-only `get_my_orders` tool, applies the policies, and writes every answer.
  - Code owns identity: `user_id` is closure-bound and is never a tool argument.
  - Code scopes data to the caller, with the same `not_found` for foreign and missing IDs, and computes neutral facts (dates, balances, business days).
  - A one-way escalation tripwire (fraud, hardship, explicit human-only requests) can only add an escalation.
  - A typed-claim output validator checks foreign IDs, order figures, action claims, waiver/limit promises and hand-off coherence. Any failure gets one repair call, then a safe escalation.
- **Options:** (a) prompt-only rules; (b) code decides eligibility and fees, and the LLM only paraphrases; (c) **the model decides, code constrains and checks**.
- **Why (c):**
  - (a) fails under injection.
  - (b) turns the LLM into a formatter, which the brief rejects.
  - With (c), data leakage and write actions are structurally impossible. Across 105 real case executions (runs 003–005) there were **0 UNSAFE_PROMISE and 0 confirmed AUTHZ_LEAK**. The single automatic AUTHZ_LEAK flag was reviewed as a false positive: a not-found reply echoing the ID the shopper typed.
  - Policy misapplication remains possible and is measured, not blocked. It is the dominant failure: GROUNDING_MISS and ROUTE_MISS on valid answers.
- **Would change my mind:**
  - If the policy-application errors that remain after prompt iteration keep recurring on the same rule (e.g. refund application, v10: missed in runs 003–005), I'd move that single fact into code.
  - The validator's own cost is 2/35 (run 004) and 3/25 (run 005 dev) cases ending in `validation_exhausted`. If manual review shows those answers were correct, I'd narrow the checks.

## ADR-2 — Full policy corpus in context, no retrieval layer
- **Decision:** all 12 policies (~2.2k tokens) sit in a static, byte-identical system prefix with `[POL-NN]` IDs. The model reports `cited_policies`, and code validates them.
- **Options:** full context; BM25/keyword top-k; embeddings + vector store; a policy-lookup tool.
- **Why:**
  - The corpus is tiny, so retrieval can only add recall misses ("push back my payment" vs "reschedule"), latency and moving parts.
  - The one-call path averaged **1.48 calls/case** on Groq (run 004). A lookup tool would add a call.
  - On the Groq path the fixed prefix produced **35.8 % cached input tokens** in run 004.
- **Would change my mind:** the prefix dominates cost. Measured on Gemini (run 003, 14 valid cases): **5.2k input tokens/case with 0 cached tokens** — the ~3.3k-token prefix is below the documented 4,096-token implicit-cache minimum. If explicit caching isn't available, **BM25 over policy sections is the next trade** (it roughly halves input). It would be judged on the same GROUNDING_MISS/ROUTE_MISS labels.

## ADR-3 — Cost/latency at 100k questions/day, $50/day, p95 ≤ 3 s
- **Decision:**
  - A small model (Flash-Lite class) with minimal/low reasoning.
  - At most 1 tool round: policy and escalation questions take 1 call, order questions 2.
  - Capped output; failover to a second model on overload; a batch-level primary-health cooldown; a safe escalation instead of long retries.
- **Options:** a larger model; always 2 calls; prefetching the caller's orders into one call; prefix caching; a smaller prefix via retrieval.
- **Why:** the budget is $50 / 100k = **$0.0005/question**, and only a small model with mostly single-call answers can approach it.
- **Measured:**
  - Gemini 3.1 / 3.5 Flash-Lite list prices × run-003 tokens = **$0.0015 / $0.0018 per question uncached — about 3× over budget.**
  - Groq gpt-oss-120b (run 004) service latency per case: **p50 1.16 s, p95 4.1 s**; per attempt p50 0.84 s, p95 1.3 s. The p95 misses 3 s only on 3-call (repair) cases.
- **What I'd trade, in order:**
  1. **Get the prefix cached:** explicit cache, or pad the prefix past the minimum. That is about 5–6× cheaper input; the estimate is **≈ $0.0006/question at 3.1 Flash-Lite prices** from the measured tokens.
  2. **Shrink the prefix with retrieval** (ADR-2).
  3. **Cut repair calls,** which drive the p95 tail, via stricter structured output.
  4. **Prefetch a minimal order summary** so order questions take one call.
  5. **On timeout, escalate rather than retry.**
- **Would change my mind:**
  - A measured cache-hit rate above 80 % on the production provider.
  - Or: a small model whose quality holds without the repair path.
  - Or: an **availability incident** like runs 001–003, when provider-wide 503s left 21–30 of 35 cases in safe failure. That argues for a second provider with separate capacity over a cheaper single model.
