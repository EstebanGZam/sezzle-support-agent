# Offline scorer

`score.py` evaluates one JSONL case set against one `answers.jsonl` file without
importing the support-agent implementation or making network calls.

```bash
uv run python evals/score.py cases/golden_visible.jsonl answers.jsonl \
  --trace trace.jsonl --set-name golden \
  --price-in 0.10 --price-out 0.40 \
  --out score.md --json score.json
```

`--out` defaults to `score.md`; `--json` is optional. Input and output prices are
USD per one million tokens and must be supplied together. Cached tokens are reported
separately and treated as a subset of input tokens for cost calculation because the
CLI has one input price. Record the price source URL and run date in the run's
`config.json` as required by `specs/evaluation.md`.

The report keeps regex pass, exact-route accuracy, and combined case pass separate.
It includes the set aggregate, primary-category aggregates, secondary-category and
expected-route coverage, and a 4×4 route confusion matrix. Percentiles use the
nearest-rank method.

Automatic labels cover the cheap deterministic checks: `CONTRACT`,
`PROVIDER_ERROR`, `AUTHZ_LEAK` candidates, `FRAUD_READBACK`, `UNSAFE_PROMISE`,
`UNDER_ESCALATION`, `OVER_ESCALATION`, and `ROUTE_MISS`. The Markdown case table
reserves explicit manual-label and evidence columns for the taxonomy decisions that
require policy review. Global safety labels are diagnostic and do not change regex,
route, or case pass results. Golden v05, v07, and v10 are marked `weak_check` without
changing their scores.

Trace metrics include end-to-end latency, semantic calls, transport attempts, input,
output and cached tokens, cached-token ratio, optional modeled cost/question, and
fallback, repair, and safe-failure rates. The report explicitly compares latency p95
with the 3-second target and modeled cost/question with the $0.0005 budget. The scorer
reports malformed, missing, and extra answer identifiers rather than silently
dropping them.
