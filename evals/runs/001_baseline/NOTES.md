# Run 001 — baseline (first real run; preserved unedited)

- Code SHA and prompt version: see each `config.json`.
- Sets: `golden` (10) and `adversarial_dev` (25). Holdout untouched.
- Model: primary `gemini-3.5-flash-lite`, fallback `gemini-3.1-flash-lite`; credential `GOOGLE_API_KEY` (fingerprint recorded in `config.json`, paid tier per P-007).
- Prices used for `$ / question`: $0.30 / 1M input, $2.50 / 1M output (ai.google.dev pricing page, 2026-09-24 snapshot).
- Command: `env -u GEMINI_API_KEY uv run --env-file .env python run_cases.py <set> <dir>/answers.jsonl --trace <dir>/trace.jsonl --config <dir>/config.json`, then `evals/score.py … --price-in 0.30 --price-out 2.50`.

## Result (from `score.md`)
| Set | Case pass | Regex pass | Route accuracy | Safe failures |
|---|---|---|---|---|
| golden | 1/10 | 1/10 | 4/10 | 10/10 |
| adversarial_dev | 2/25 | 4/25 | 9/25 | 18/25 |

## Diagnosis (first pass)
- **Dominant failure class: PROVIDER_ERROR (28/35 cases).**
  - Per-case traces show `server_5xx`/`timeout` on both transport attempts, all on the primary model.
  - Synthetic probes run right after the baseline (no assessment content) returned `HTTP 503 UNAVAILABLE: "This model is currently experiencing high demand…"` and `HTTP 504 DEADLINE_EXCEEDED` for `gemini-3.5-flash-lite`.
  - `gemini-3.1-flash-lite` mostly succeeded, in 2–5 s.
- **Our defect exposed by it:**
  - `LLM_MAX_ATTEMPTS=2` is shared by primary + fallback, and the same-model retry on 5xx runs first. So the budget is spent on the overloaded primary and **the fallback model is never tried** (0 fallback attempts in 35 cases).
  - The architecture §7 table allowed this combination; the defect is in the policy, not a coding slip.
- **Latency:** successful primary calls took ~6–8 s, versus ~1.2–1.5 s in the earlier synthetic smoke test. That is consistent with provider-side overload at run time, and the numbers are not representative for the ADR-3 SLO.
- **LLM behaviour** could only be observed on the 7 cases that got answers; it is analysed after the resilience fix, when behaviour failures aren't masked by provider errors.
