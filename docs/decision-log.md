# Engineering Decision Log (owner decisions)

The three graded ADRs are in `DECISIONS.md` (exactly three, as the brief requires). This log records **who decided what**: owner decisions are distinguished from agent recommendations. Agents may propose; only the owner approves.

| # | Date | Decision | Decided by | Source | Supersedes / notes |
|---|---|---|---|---|---|
| OD-01 | 2026-09-27 | Organize copies of the assessment materials in the documented structure with a provenance/integrity manifest; private repository | **Owner** | P-004 §1 | Implemented: `assessment/MANIFEST.md`, `assessment/SHA256SUMS` |
| OD-02 | 2026-09-27 | Python 3.12 + required CLI contract; no Spring Boot or web framework without a concrete requirement | **Owner** | P-004 §2 | — |
| OD-03 | 2026-09-27 | Native Google GenAI SDK; explicit controlled tool-calling loop; lightweight config abstraction | **Owner** | P-004 §3 | — |
| OD-04 | 2026-09-27 | Complete policy corpus in context initially; no embeddings/vector infra without measured justification | **Owner** | P-004 §4 | → ADR-2 |
| OD-05 | 2026-09-27 | Stateless isolated context per case; shared resources initialized once; sequential execution with a clean path to bounded concurrency | **Owner** | P-004 §5 | → `specs/architecture.md` §9 |
| OD-06 | 2026-09-27 | Structural security controls, scoped read-only tools, strict authorization, consumption limits, I/O validation, safe escalation | **Owner** | P-004 §6 | → `specs/security.md` |
| OD-07 | 2026-09-27 | Gemini Flash-Lite; compare variants via a minimal smoke test **before** locking the primary; configurable compatible fallback | **Owner** | P-004 §7 | Smoke test done (synthetic content) — **primary model not yet locked** (pending owner) |
| OD-08 | 2026-09-27 | Evaluation: pytest, deterministic fake-model tests, reproducible LLM evals, local traces, independent adversarial review | **Owner** | P-004 §8 | → `specs/evaluation.md` |
| OD-09 | 2026-09-27 | uv + lockfile, Conventional Commits, lightweight SDD, private GitHub, proportionate CI; deliverable also as a self-contained ZIP | **Owner** | P-004 §9 | Remote repo creation still needs authorization |
| OD-10 | 2026-09-27 | Orchestrator lead coordinates; one principal implementer; separate evaluation agent; Codex independent reviewer; Claude Cloud optional | **Owner** | P-004 §10 | → `docs/agent-plan.md` |
| OD-11 | 2026-09-27 | Deployment excluded from the mandatory scope; protected 21-day demo may be a later separate phase | **Owner** | P-004 | — |
| OD-12 | 2026-09-27 | Deterministic business-rule validation and calculations are allowed where they improve correctness/safety without replacing the LLM; the boundary is documented as an ADR; no overfitting to golden cases | **Owner** | P-004 "Important clarification" | → ADR-1, `specs/architecture.md` §4 |
| OD-13 | 2026-09-27 | Do not contact the hiring manager; record ambiguities as assumptions | **Owner** | P-004 | → `specs/assumptions.md` |
| OD-14 | 2026-09-27 | The owner manages assessment time | **Owner** | P-004 | — |
| OD-15 | *pending* | Primary + fallback Gemini Flash-Lite model IDs (smoke-test evidence in `docs/readiness-checklist.md` §C) | **Owner (pending)** | — | Blocks IP-01 (config has no default model) |

## Agent recommendations — PROPOSED, pending owner approval as a bundle

These are written into the specs as proposals (marked `[AR-nn]`). They are **not** owner-approved until the owner says so at implementation start. The owner may accept, change, or reject each one.

| # | Recommendation | Origin | Where |
|---|---|---|---|
| AR-01 | ≤1 tool round; call #2 with tool mode `none` | Codex review (A-009) + lead | architecture §5 |
| AR-02 | Route derived in code from escalation signal + actual tool execution + a model-emitted `policy_applied` flag (not citations) | Codex reviews A-009, R-00 | architecture §3.3, §6 |
| AR-03 | Typed-claim output validator (pass/warn/fail) instead of a global numeric firewall | Codex reviews A-009, R-00 | security §4 |
| AR-04 | Neutral facts only in the baseline; policy-conclusion facts only as measured iterations | Codex review, reconciled with OD-12 | architecture §4 |
| AR-05 | Holdout adversarial set stored outside the repo until the final run | Lead | evaluation spec |
| AR-06 | Free-tier key never used as automatic fallback | Gemini research + smoke test | architecture §7, A-10 |
| AR-07 | One-way escalation tripwire extended to explicit human-only action requests and explicit human requests (precision-first; never writes answers) | Codex review R-00 #7 | security §3, architecture §5 |
| AR-08 | Scope tiers and cut order | Codex review R-00 #12 | tasks.md |

## Pending owner decisions
See `docs/readiness-checklist.md` §"Decisions requiring owner approval".
