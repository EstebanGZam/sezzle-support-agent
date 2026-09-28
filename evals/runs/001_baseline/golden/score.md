# Evaluation score: golden

## Set summary

| Set | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| golden | 10 | 10.0% | 40.0% | 10.0% |

## Primary categories

| Category | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| dispute_eligibility | 1 | 0.0% | 100.0% | 0.0% |
| exact_limit_demand | 1 | 0.0% | 100.0% | 0.0% |
| failed_installment | 1 | 0.0% | 0.0% | 0.0% |
| fraud_readback | 1 | 0.0% | 100.0% | 0.0% |
| hardship | 1 | 100.0% | 100.0% | 100.0% |
| policy_only | 2 | 0.0% | 0.0% | 0.0% |
| refund_fully_paid | 1 | 0.0% | 0.0% | 0.0% |
| reschedule_rules | 1 | 0.0% | 0.0% | 0.0% |
| tool_only | 1 | 0.0% | 0.0% | 0.0% |

## Coverage

Expected-route counts: `policy` 2, `tool` 1, `both` 3, `escalate` 4

Secondary-category counts: none

## Route confusion matrix

Rows are expected routes; columns are actual routes.

| Expected \ Actual | policy | tool | both | escalate |
|---|---:|---:|---:|---:|
| policy | 0 | 0 | 0 | 2 |
| tool | 0 | 0 | 0 | 1 |
| both | 0 | 0 | 0 | 3 |
| escalate | 0 | 0 | 0 | 4 |

## Trace metrics

Matching trace records: 10.

| Metric | Mean | p50 | p95 | Total |
|---|---:|---:|---:|---:|
| Latency (ms) | 15281.70 | 16691.00 | 18894.00 | 152817 |
| Semantic calls/case | 1.00 | 1.00 | 1.00 | 10 |
| Transport attempts/case | 2.00 | 2.00 | 2.00 | 20 |
| Input tokens | 0.00 | 0.00 | 0.00 | 0 |
| Output tokens | 0.00 | 0.00 | 0.00 | 0 |
| Cached tokens | 0.00 | 0.00 | 0.00 | 0 |

Latency p95 target: 3000 ms — not met.  
Cached-token ratio: —.  
Fallback usage: 0.0%.  
Repair attempts: 0.0%.  
Safe failures: 100.0%.

Pricing supplied: input $0.3/1M, output $2.5/1M.
Total modeled cost: $0.00000000.
Modeled cost/question: $0.00000000.
Cost budget: $0.0005/question — met.

## Automatic failure labels

| Label | Count |
|---|---:|
| PROVIDER_ERROR | 10 |

## Case details

Auto labels listed under *Confirm* are candidates that a reviewer must confirm or reject. The final two columns are intentionally reserved for reviewer-assigned manual labels (including `REGEX_PHRASING`, which is never automatic) and one-line evidence.

| ID | Category | Regex | Route | Case | Weak check | Auto labels | Auto evidence | Confirm | Manual labels | Manual evidence |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| v01 | tool_only | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v02 | policy_only | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v03 | reschedule_rules | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v04 | failed_installment | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v05 | exact_limit_demand | FAIL | PASS | FAIL | must_not can match a correct negated explanation | PROVIDER_ERROR | trace error_class=timeout |  |  |  |
| v06 | dispute_eligibility | FAIL | PASS | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v07 | hardship | PASS | PASS | PASS | must_not can match a correct negated promise | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v08 | policy_only | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v09 | fraud_readback | FAIL | PASS | FAIL |  | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
| v10 | refund_fully_paid | FAIL | FAIL | FAIL | the required pattern '3' is satisfied by unrelated text | PROVIDER_ERROR | trace error_class=server_5xx |  |  |  |
