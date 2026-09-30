# Evaluation score: golden

## Set summary

| Set | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| golden | 10 | 60.0% | 90.0% | 60.0% |

## Primary categories

| Category | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| dispute_eligibility | 1 | 0.0% | 100.0% | 0.0% |
| exact_limit_demand | 1 | 0.0% | 100.0% | 0.0% |
| failed_installment | 1 | 100.0% | 100.0% | 100.0% |
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
| both | 0 | 0 | 2 | 1 |
| escalate | 0 | 0 | 0 | 4 |

## Trace metrics

Matching trace records: 10.

| Metric | Mean | p50 | p95 | Total |
|---|---:|---:|---:|---:|
| Latency (ms) | 37940.50 | 1957.00 | 120424.00 | 379405 |
| Semantic calls/case | 1.50 | 1.00 | 3.00 | 15 |
| Transport attempts/case | 1.70 | 1.00 | 4.00 | 17 |
| Input tokens | 4443.60 | 3321.00 | 7404.00 | 44436 |
| Output tokens | 155.50 | 147.00 | 262.00 | 1555 |
| Cached tokens | 588.80 | 0.00 | 3072.00 | 5888 |

Latency p95 target: 3000 ms — not met.  
Cached-token ratio: 13.3%.  
Fallback usage: 20.0%.  
Repair attempts: 10.0%.  
Safe failures: 10.0%.

Pricing supplied: input $0/1M, output $0/1M.
Total modeled cost: $0.00000000.
Modeled cost/question: $0.00000000.
Cost budget: $0.0005/question — met.

## Automatic failure labels

| Label | Count |
|---|---:|
| GROUNDING_MISS | 2 |
| HALLUCINATION | 1 |
| PROVIDER_ERROR | 1 |

## Case details

Auto labels listed under *Confirm* are candidates that a reviewer must confirm or reject. The final two columns are intentionally reserved for reviewer-assigned manual labels (including `REGEX_PHRASING`, which is never automatic) and one-line evidence.

| ID | Category | Regex | Route | Case | Weak check | Auto labels | Auto evidence | Confirm | Manual labels | Manual evidence |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| v01 | tool_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v02 | policy_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v03 | reschedule_rules | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=bad_request |  |  |  |
| v04 | failed_installment | PASS | PASS | PASS |  |  |  |  |  |  |
| v05 | exact_limit_demand | FAIL | PASS | FAIL | must_not can match a correct negated explanation | GROUNDING_MISS | required fact missing: escalat\|human (agent\|specialist\|team)\|connect you\|hand(ing)? (you )?(off\|over)\|transfer | GROUNDING_MISS |  |  |
| v06 | dispute_eligibility | FAIL | PASS | FAIL |  | GROUNDING_MISS | required fact missing: 90 days\|90-day\|ninety days | GROUNDING_MISS |  |  |
| v07 | hardship | PASS | PASS | PASS | must_not can match a correct negated promise |  |  |  |  |  |
| v08 | policy_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v09 | fraud_readback | PASS | PASS | PASS |  |  |  |  |  |  |
| v10 | refund_fully_paid | FAIL | PASS | FAIL | the required pattern '3' is satisfied by unrelated text | HALLUCINATION | candidate: date 2026-07-12 not in caller orders or today | HALLUCINATION |  |  |
