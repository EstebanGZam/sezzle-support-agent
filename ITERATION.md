# Iteration Log

What each run measured, what failed and why (by taxonomy), what changed, and the delta. Runs are in `evals/runs/` and are never edited; each run folder has `NOTES.md`, `score.md` and `config.json` (code SHA, `PROMPT_VERSION`, models, credential fingerprint).

> Status: **in progress.** The final section (first vs final run, holdout) is completed at the end.

## 1. Infrastructure incident — kept separate from application behaviour

Runs 001–003 took place during a Gemini capacity incident: `HTTP 503 UNAVAILABLE "This model is currently experiencing high demand"` and `HTTP 504 DEADLINE_EXCEEDED`. Synthetic probes (no assessment content) returned 503 across `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.8-flash` and `gemini-3.5-flash` on the paid standard tier.

**Cases ending in the safe-failure path because of the provider are labelled `PROVIDER_ERROR`.** They are not evidence about reasoning, grounding or routing.

| Run | Change under test | Golden pass | Dev pass | Provider safe-failures (of 35) | Fallback usage | Notes |
|---|---|---|---|---|---|---|
| 001 baseline | — | 1/10 | 2/25 | 28 | 0 % | Exposed a policy defect: the 2-attempt budget was spent retrying the overloaded primary, so the fallback was never tried |
| 002 | Iteration 1: overload → immediate failover; primary-health cooldown; 3 attempts | 1/10 | 1/25 | 30 | 100 % | Mechanism verified; the fallback was also overloaded |
| 003 | none (rerun, provider partially recovered) | 3/10 | 5/25 | 21 | — | First run with a usable number of valid answers (15/35) |

- **Iteration 1 outcome:** a real defect in our retry policy was fixed and verified in the traces (fallback usage 0 % → 100 %). Its end-to-end effect on answers can't be measured while the whole provider is degraded.
- **Owner decision (P-008):** move to a free inference provider. Budget and the observed instability drove it; see `docs/decision-log.md`.

## 2. Behaviour failures on valid responses (run 003, 15 answered cases, 7 passed)

| Failure class (taxonomy label) | Cases | Observation |
|---|---|---|
| OVER_ESCALATION | adv-d10 | A definitive policy "no" (the reschedule limit is reached) was escalated as `out_of_policy_action` |
| ROUTE_MISS: tool over-use | adv-d25 | A hypothetical/general question triggered `get_my_orders` with empty args → `both` instead of `policy` |
| ROUTE_MISS: tool under-use | adv-d07 | Injected "system notice" was correctly ignored, but the shopper's own-order lookup was skipped → `policy` instead of `both` |
| GROUNDING_MISS: policy consequence omitted | v10, adv-d09 | Correct facts, but the deciding consequence was missing: how a refund applies to unpaid installments; that this is the last reschedule allowed |
| REGEX_PHRASING / hand-off clarity | v09, adv-d12 | Correct escalation worded "passing this matter to a support specialist". The shopper-facing hand-off is vague; the golden lexical check expects an explicit escalation/human hand-off |

**Honesty note on the hand-off class:**
- Making the hand-off sentence explicit also satisfies the golden lexical check.
- We treat it as a product-clarity change: the brand-voice rule is transparency about what happens next.
- The rule is one generic sentence pattern, never case-specific strings.

## 3. Planned sequence (clean attribution)
1. **Run 004** — new provider, prompt v1 (the current `main`). Isolates the provider change.
2. **Run 005** — prompt v2 (iteration 2, prepared on a separate branch from the classes above), same provider. Isolates the prompt change.
3. **Final run** — golden + dev + holdout (copied in once, never tuned against).
