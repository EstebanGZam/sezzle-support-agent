# Skeptical architecture review

The recommendation is directionally sound, especially the user-bound read-only tool, full-corpus prompting, and CLI-first scope. But it spends too much of a two-hour exercise on defensive infrastructure and risks implementing the interesting reasoning outside the LLM. `PROMPT.md` says the grading order is decisions, iteration, LLM engineering, escalation/authorization, then AI-tool direction; the work plan should mirror that order.

## Scope and engineering balance

The first cuts should be the second provider/fallback architecture, two-round tool loop, universal number/date validator, canary mechanism, broad derived-fact engine, and any session/concurrency framework. Keep one paid model, one tool round, Pydantic output parsing, bounded timeout/retry, and a plain safe error response. `uv`, pytest, and ruff are cheap if familiar, but provider failover and a second execution shape create branches that consume the time needed for measured iteration. The brief explicitly rewards an honest unfinished note (`PROMPT.md`, “Time budget”) and does not grade provider choice or scaffolding.

Conversely, the recommendation is under-specified where marks concentrate. `DECISIONS.md` must contain exactly three records, each short and falsifiable; one should quantify the cost/latency trade rather than merely naming a cheap model. The first and final *full* visible runs need preserved outputs, score deltas, and a failure taxonomy—not just “committed runs.” `PROMPTS.md` must include both build prompts and runtime system prompts. Structural guarantees should be demonstrable: user identity cannot be model-controlled, foreign and absent order IDs are indistinguishable, and fresh per-case state prevents cross-user leakage. Tests should explicitly cover those properties.

## The “LLM is the assignment” boundary

`PROMPT.md` expressly welcomes deterministic pre-filters, authorization, and output validation; it rejects deterministic routing-and-answering *instead of* the model. A fraud/hardship tripwire is therefore defensible as a one-way safety override, provided the model still produces the empathetic, policy-grounded response and the tripwire is not a general intent router. It directly protects v07 and v09. Do not expand it into regex routing for every visible case.

Derived facts are safe when they are mechanical normalization: filtering to the bound user, sorting installments, or exposing frozen `today` from `DATA-orders.json`. They cross the line when they encode policy conclusions such as `reschedule_eligible`, `fee`, `failed=>repay`, dispute eligibility, or refund disposition. Those are precisely the cross-source inferences v03, v04, and v10 test. Return authorized raw order fields plus perhaps neutral arithmetic; ask the model to combine them with policy. The fail-closed template is acceptable only for provider/validation failure. If it becomes the ordinary answer for v05–v09, the code—not the model—is answering.

## Route ownership, using v01–v10

Neither pure model labeling nor pure trace derivation is sufficient. Use a hybrid: the model emits `escalation_reason` and cited policy IDs; code observes whether the order tool actually ran, validates citations, and derives the label. A valid escalation reason or safety override wins and yields `escalate`; otherwise tool-use plus citations yields `both`, tool only yields `tool`, and citations only yields `policy`.

That rule matches v01 (`tool`), v02/v08 (`policy`), and v03/v04/v10 (`both`). It also handles the important semantic wrinkle that v06 explains dispute policy yet is labeled `escalate`, as are v05, v07, and v09. Pure trace derivation would call v06 “policy”; pure model output can contradict its actual behavior. Because all policies are present in the prompt, “policy used” must come from validated cited IDs, not mere prompt availability. v06 also names Bloom & Vine ambiguously—u003 has two such orders—so the assistant should explain and escalate without guessing an order.

## Loop shape and production ADR

For this assessment, a real tool loop is better than prefetch. It demonstrates capability selection, keeps irrelevant account data out of the prompt, makes v01/v03/v04/v10 tool use observable, and preserves meaningful route evidence. Prefetching every order makes one call faster but weakens data minimization and turns `tool` versus `policy` into an unverifiable model classification.

Cap the MVP at one tool call/one continuation, not two tool rounds. Policy-only and escalation questions finish in one inference; account questions take two. In the ADR, acknowledge that two inferences may threaten p95 <=3s and that 100k/day at $50/day permits only $0.0005 per question. Propose cached policy prefixes, a narrow tool response, short output, measured token/latency distributions, and—only if measurements fail—a one-call prefetch of a minimal authorized account summary. Do not claim the named model meets the SLO without measurements.

## Validation without a brittle numeric firewall

A global “all numbers/dates must be in the grounded set” validator will reject legitimate paraphrases (`25%` versus “a quarter,” `2 weeks` versus “14 days,” July 11 versus `2026-07-11`) and incidental safe terms such as “2FA” or “pay-in-4.” It may also accept a wrong `$10` because that number appears in an unrelated policy, or mishandle ranges such as “3–10 business days” in v10 and the 90/15-day rules in v06.

Prefer a simpler boundary: strict schema/enums, known policy IDs, no foreign order IDs, no prohibited action claims, and no order-specific amount/date absent from the *actual tool result*, after canonicalizing currency and dates. Let evaluation catch broader semantic mistakes. A single repair attempt is reasonable; otherwise return an explicit system-failure escalation, not a substantive deterministic policy answer.

## Isolation and missing requirements

The contract is batch, single-turn (`python3 run_cases.py ...`), so sessions are unjustified. Load policy text and immutable order data once; for each JSONL row create fresh messages, tool trace, and a tool closure bound to that row’s `user_id`. Pure read-only lookup functions may safely share immutable resources. Sequential execution is enough; production concurrency can use stateless request objects without conversation memory.

The design must also explicitly use the fixture’s frozen `today`, emit only `{id, route, answer}` despite richer internal output, preserve first and final answer files, include exactly three <=10-line ADRs, log AI prompts, and provide the half-page README with honest unfinished work. Add hostile tests for prompt injection, foreign/nonexistent IDs, merchant ambiguity, and cross-case leakage. Note the fixture anomaly in v04: trust the recorded `failed` status even though its due date is after frozen `today`; do not silently “correct” source data.

## Top 5 changes I'd make

1. Remove provider fallback, the second tool round, and session/concurrency machinery.
2. Return raw authorized order state; delete policy-conclusion derived facts.
3. Derive route hybridly from validated escalation, actual tool use, and cited policies.
4. Replace the global numeric validator with narrow order-claim and action-claim checks.
5. Spend the saved time on three strong ADRs, preserved first/final runs, a failure taxonomy, and `PROMPTS.md`.
