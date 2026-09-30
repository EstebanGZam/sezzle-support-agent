# Run 003 — same code/config as run 002, provider partially recovered (preserved unedited)

- **Purpose:** measure LLM behaviour once provider capacity improved.
- **Probe before the run** (synthetic): 3.5-flash-lite 1/3 ok; 3.1-flash-lite 3/3 ok.
- **No code change vs run 002** (same git SHA line in `config.json`).

| Set | Case pass | Regex pass | Route acc. | Safe failures | Successful attempts by model | p50 / p95 | $/question* |
|---|---|---|---|---|---|---|---|
| golden | 3/10 | 3/10 | 7/10 | 6/10 | 3.1-fl 8 | 9.3 s / 22.4 s | $0.00092 |
| adversarial_dev | 5/25 | 8/25 | 11/25 | 15/25 | 3.1-fl 18, 3.5-fl 4 | 16.8 s / 22.8 s | $0.00104 |

\* List prices $0.30/$2.50 per 1M (3.5 Flash-Lite). Most successful calls actually went to 3.1 Flash-Lite ($0.25/$1.50), so the figure is an upper bound. Cached-token ratio: 0.0 (implicit caching did not apply).

## Diagnosis
- **PROVIDER_ERROR is still dominant** (21/35 safe failures: overloaded 14, timeout 7), so the provider incident is ongoing.
- **The primary-health cooldown works:** successful traffic shifted to the fallback.
- **Measured tokens:** mean input ≈ 2.7–3.0k and output ≈ 46–55 per case, with no cache hits. This is first real evidence for ADR-3: at list prices, uncached full-context runs above the $0.0005 budget once two calls are needed.
- **Behaviour on answered cases is analysed in ITERATION.md.**
