# Decision Records

> **Status: PROPOSED.** The direction is owner-approved (`docs/decision-log.md`). The wording is final only after measured runs. Every `[MEASURE: …]` must be replaced with numbers from `evals/runs/` before submission — never with estimates presented as measurements. Format required by the brief: *decision · options considered · why · what evidence would change my mind*; exactly 3 records, each ≤ ~10 lines.

## ADR-1 — Guardrails live in code; the model interprets and answers
- **Decision:**
  - The LLM reads each request, decides whether to call the single read-only `get_my_orders` tool, applies the policies, and writes every answer.
  - Code owns identity: `user_id` is bound by closure, never passed as a tool argument.
  - Code scopes data to the caller and returns the same `not_found` for another shopper's order and a missing one.
  - Code computes neutral facts (dates, balances, business days) and runs a one-way escalation tripwire (fraud, hardship, explicit human-only requests).
  - A typed-claim output validator checks foreign IDs, order figures, action claims, waiver/limit promises and hand-off coherence.
- **Options:** (a) prompt-only rules; (b) code decides policy outcomes such as eligibility and fees, and the LLM only paraphrases; (c) **the model decides, code constrains and checks**.
- **Why (c):**
  - (a) fails under injection.
  - (b) makes the LLM a formatter, which the brief rejects.
  - (c) makes data leakage and write actions structurally impossible, and catches most action claims and ungrounded order figures.
  - Policy misapplication (e.g. quoting the wrong fee) is still possible. It is measured by the evals, not blocked.
- **Would change my mind:**
  - Policy-application errors that prompts can't fix (`[MEASURE: n cases, label]`) → move that single fact into code as a measured iteration.
  - Validator false-positive rate above `[MEASURE: %]` → narrow the checks.

## ADR-2 — Full policy corpus in context, no retrieval layer
- **Decision:** all 12 policies (~2.2k tokens) sit in a static, byte-identical system prefix with `[POL-NN]` IDs. The model reports `cited_policies`, and code validates them against the corpus.
- **Options:** full context; BM25/keyword top-k; embeddings + vector store; a policy-lookup tool.
- **Why:**
  - The corpus is tiny, so retrieval can only add recall misses ("push back my payment" vs "reschedule"), latency and moving parts.
  - A fixed prefix is cacheable, and its citations are checkable.
  - A lookup tool adds a round trip against p95 ≤ 3 s.
- **Would change my mind:**
  - The corpus grows beyond ~30–50k tokens.
  - The prefix dominates $/question and caching is unavailable (ADR-3).
  - Grounding misses are traced to distraction from irrelevant policies (`[MEASURE: GROUNDING_MISS by cause]`).
  - Then: BM25 over sections, evaluated on the same case sets.

## ADR-3 — Cost/latency at 100k questions/day, $50/day, p95 ≤ 3 s
- **Decision:**
  - Model: Gemini Flash-Lite `[PRIMARY — owner decision OD-15]` with minimal thinking.
  - At most 1 tool round: policy and escalation questions take 1 call, order questions take 2.
  - Capped output; one bounded retry, then failover to `[FALLBACK]`; a safe escalation instead of long retries.
- **Options:** a larger model; a 2-call loop for every question; one call with the shopper's orders prefetched; prefix caching; a smaller prefix via retrieval.
- **Why:** the budget is $50 / 100k = **$0.0005 per question**. Flash-Lite with one call for most intents is the only option that fits without dropping the tool loop that keeps order data minimal and observable. Measured: `[MEASURE: mean input/cached/output tokens; $/question; p50/p95 ms]`.
- **What I'd trade, in order:**
  1. Cache the prefix, or shrink it. At 3.1 Flash-Lite list prices, the ~3.3k-token prefix alone costs about $82/day uncached vs about $8/day cached (arithmetic from list prices, not measured).
  2. Prefetch a minimal authorized order summary, so order questions take one call. This gives up data minimization and visibility of when the tool is used.
  3. On timeout, escalate rather than retry past the p95 budget.
- **Would change my mind:**
  - Measured p95 above 3 s on 2-call cases. The synthetic smoke test (n = 3, tiny prompts, free tier) gave medians of 2.67 s (3.5 Flash-Lite) and 3.04 s (3.1 Flash-Lite).
  - Cache-hit ratio `[MEASURE]`.
  - Flash-Lite quality failures that a larger model fixes for less than $0.0005 per question.
