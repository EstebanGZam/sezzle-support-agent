# Run 002 — iteration 1 (resilience policy), preserved unedited

- **Change under test (one change):** overload (`503 UNAVAILABLE`, `504 DEADLINE_EXCEEDED`) → immediate failover to the fallback model, with no same-model retry. Adds a batch-scoped primary-health cooldown, and the attempt budget goes to 3 (primary → fallback → one same-model retry). Commit and config are in `config.json`.
- **Same sets, prices and command as run 001.** `LLM_MAX_ATTEMPTS=3` and `LLM_TIMEOUT_S=10` were set on the command line; the owner's local `.env` still had the old example values.

## Result
| Set | Case pass | Route acc. | Safe failures | Fallback usage | p50 / p95 latency |
|---|---|---|---|---|---|
| golden | 1/10 (001: 1/10) | 4/10 | 9/10 (001: 10/10) | 100 % (001: 0 %) | 19.3 s / 23.2 s |
| adversarial_dev | 1/25 (001: 2/25) | 7/25 | 21/25 (001: 18/25) | 100 % (001: 0 %) | 12.2 s / 27.9 s |

## Diagnosis
- **The mechanism works.** Every case now reached the fallback model: fallback usage went from 0 % to 100 %.
- **The outcome didn't improve, because the fallback was overloaded too.** Terminal classes: golden `overloaded` 8, `timeout` 1; dev `overloaded` 17, `timeout` 4.
- **Synthetic probes right after the run** (no assessment content) show the overload is provider-wide, not limited to our models:
  - 3 calls each to `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-3.8-flash` and `gemini-3.5-flash`;
  - mostly `503`, with occasional `200` after 5–27 s; `serviceTier: standard`.
- **Conclusion:** during runs 001–002, PROVIDER_ERROR reflects a provider-capacity incident. Neither run measures LLM behaviour or representative latency. The resilience change is kept, because it fixes a real policy defect. A rerun is needed once provider capacity recovers.
- **Cost of this run** (listed prices): $0.000234/question (golden) and $0.000588/question (dev). Few calls completed, so this isn't representative.
