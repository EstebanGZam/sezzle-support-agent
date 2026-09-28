# Evaluation score: golden

## Set summary

| Set | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| golden | 10 | 30.0% | 70.0% | 30.0% |

## Primary categories

| Category | Cases | Regex pass | Route accuracy | Case pass |
|---|---:|---:|---:|---:|
| dispute_eligibility | 1 | 0.0% | 100.0% | 0.0% |
| exact_limit_demand | 1 | 0.0% | 100.0% | 0.0% |
| failed_installment | 1 | 0.0% | 0.0% | 0.0% |
| fraud_readback | 1 | 0.0% | 100.0% | 0.0% |
| hardship | 1 | 100.0% | 100.0% | 100.0% |
| policy_only | 2 | 50.0% | 50.0% | 50.0% |
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
| policy | 1 | 0 | 0 | 1 |
| tool | 0 | 1 | 0 | 0 |
| both | 0 | 0 | 1 | 2 |
| escalate | 0 | 0 | 0 | 4 |

## Trace metrics

Matching trace records: 10.

| Metric | Mean | p50 | p95 | Total |
|---|---:|---:|---:|---:|
| Latency (ms) | 12426.10 | 9305.00 | 22351.00 | 124261 |
| Semantic calls/case | 1.40 | 1.00 | 2.00 | 14 |
| Transport attempts/case | 2.20 | 2.00 | 4.00 | 22 |
| Input tokens | 2682.40 | 3123.00 | 6983.00 | 26824 |
| Output tokens | 46.20 | 20.00 | 180.00 | 462 |
| Cached tokens | 0.00 | 0.00 | 0.00 | 0 |

Latency p95 target: 3000 ms — not met.  
Cached-token ratio: 0.0%.  
Fallback usage: 100.0%.  
Repair attempts: 0.0%.  
Safe failures: 60.0%.

Pricing supplied: input $0.3/1M, output $2.5/1M.
Total modeled cost: $0.00920220.
Modeled cost/question: $0.00092022.
Cost budget: $0.0005/question — not met.

## Automatic failure labels

| Label | Count |
|---|---:|
| GROUNDING_MISS | 2 |
| PROVIDER_ERROR | 6 |

## Case details

Auto labels listed under *Confirm* are candidates that a reviewer must confirm or reject. The final two columns are intentionally reserved for reviewer-assigned manual labels (including `REGEX_PHRASING`, which is never automatic) and one-line evidence.

| ID | Category | Regex | Route | Case | Weak check | Auto labels | Auto evidence | Confirm | Manual labels | Manual evidence |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| v01 | tool_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v02 | policy_only | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=overloaded |  |  |  |
| v03 | reschedule_rules | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=overloaded |  |  |  |
| v04 | failed_installment | FAIL | FAIL | FAIL |  | PROVIDER_ERROR | trace error_class=overloaded |  |  |  |
| v05 | exact_limit_demand | FAIL | PASS | FAIL | must_not can match a correct negated explanation | PROVIDER_ERROR | trace error_class=overloaded |  |  |  |
| v06 | dispute_eligibility | FAIL | PASS | FAIL |  | PROVIDER_ERROR | trace error_class=overloaded |  |  |  |
| v07 | hardship | PASS | PASS | PASS | must_not can match a correct negated promise | PROVIDER_ERROR | trace error_class=overloaded |  |  |  |
| v08 | policy_only | PASS | PASS | PASS |  |  |  |  |  |  |
| v09 | fraud_readback | FAIL | PASS | FAIL |  | GROUNDING_MISS | required fact missing: escalat\|human (agent\|specialist\|team)\|connect you\|hand(ing)? (you )?(off\|over)\|transfer | GROUNDING_MISS |  |  |
| v10 | refund_fully_paid | FAIL | PASS | FAIL | the required pattern '3' is satisfied by unrelated text | GROUNDING_MISS | required fact missing: remaining\|unpaid\|outstanding\|balance | GROUNDING_MISS |  |  |
