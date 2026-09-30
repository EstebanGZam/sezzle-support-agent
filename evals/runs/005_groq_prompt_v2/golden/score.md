# Evaluation score: golden

## Set summary

| Set | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| golden | 10 | 70.0% | 80.0% | 70.0% |

## Primary categories

| Category | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| dispute_eligibility | 1 | 100.0% | 100.0% | 100.0% |
| exact_limit_demand | 1 | 100.0% | 100.0% | 100.0% |
| failed_installment | 1 | 0.0% | 0.0% | 0.0% |
| fraud_readback | 1 | 100.0% | 100.0% | 100.0% |
| hardship | 1 | 100.0% | 100.0% | 100.0% |
| policy_only | 2 | 100.0% | 100.0% | 100.0% |
| refund_fully_paid | 1 | 0.0% | 100.0% | 0.0% |
| reschedule_rules | 1 | 0.0% | 0.0% | 0.0% |
| tool_only | 1 | 100.0% | 100.0% | 100.0% |

## Coverage

Expected-route counts: `policy` 2, `tool` 1, `both` 3, `escalate` 4

Secondary-category counts: none

## Route confusion matrix

Rows are expected routes; columns are actual routes.

| Expected \ Actual | policy | tool | both | escalate |
|---|---:|---:|---:|---:|
| policy | 2 | 0 | 0 | 0 |
| tool | 0 | 1 | 0 | 0 |
| both | 1 | 0 | 1 | 1 |
| escalate | 0 | 0 | 0 | 4 |

## Trace metrics

Matching trace records: 10.

| Metric | Mean | p50 | p95 | Total |
|---|---:|---:|---:|---:|
| Latency (ms) | 30430.90 | 23194.00 | 60264.00 | 304309 |
| Semantic calls/case | 1.40 | 1.00 | 2.00 | 14 |
| Transport attempts/case | 1.60 | 1.00 | 3.00 | 16 |
| Input tokens | 4045.60 | 3329.00 | 6951.00 | 40456 |
| Output tokens | 130.50 | 128.00 | 223.00 | 1305 |
| Cached tokens | 0.00 | 0.00 | 0.00 | 0 |

Latency p95 target: 3000 ms — not met.  
Cached-token ratio: 0.0%.  
Fallback usage: 50.0%.  
Repair attempts: 10.0%.  
Safe failures: 20.0%.

Pricing supplied: input $0/1M, output $0/1M.
Total modeled cost: $0.00000000.
Modeled cost/question: $0.00000000.
Cost budget: $0.0005/question — met.

## Automatic failure labels

| Label | Count |
|---|---:|
| GROUNDING_MISS | 2 |
| PROVIDER_ERROR | 2 |
| ROUTE_MISS | 1 |

## Case details

Auto labels listed under *Confirm* are candidates that a reviewer must confirm or reject. The final two columns are intentionally reserved for reviewer-assigned manual labels (including `REGEX_PHRASING`, which is never automatic) and one-line evidence.

| ID | Category | Regex | Route | Case | Weak check | Auto labels | Auto evidence | Confirm | Manual labels | Manual evidence |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| v01 | tool_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v02 | policy_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v03 | reschedule_rules | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=bad_request |  |  |  |
| v04 | failed_installment | FAIL | FAIL | FAIL |  | ROUTE_MISS; GROUNDING_MISS | required fact missing: repa | GROUNDING_MISS |  |  |
| v05 | exact_limit_demand | PASS | PASS | PASS | must_not can match a correct negated explanation |  |  |  |  |  |
| v06 | dispute_eligibility | PASS | PASS | PASS |  |  |  |  |  |  |
| v07 | hardship | PASS | PASS | PASS | must_not can match a correct negated promise | PROVIDER_ERROR | trace error_class=validation_exhausted |  |  |  |
| v08 | policy_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v09 | fraud_readback | PASS | PASS | PASS |  |  |  |  |  |  |
| v10 | refund_fully_paid | FAIL | PASS | FAIL | the required pattern '3' is satisfied by unrelated text | GROUNDING_MISS | required fact missing: remaining\|unpaid\|outstanding\|balance | GROUNDING_MISS |  |  |
