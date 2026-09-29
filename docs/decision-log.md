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
| OD-15 | 2026-09-27 | Primary `gemini-3.5-flash-lite`, fallback `gemini-3.1-flash-lite`; selection stays configurable; compatibility verified | **Owner** | P-005 §2 | Resolves R-00 blocker #1; config defaults set |
| OD-16 | 2026-09-27 | Never switch automatically to an unpaid project/credential with different data-handling terms; failover changes the model only | **Owner** | P-005 §2 | Supersedes AR-06 (now owner-directed) |
| OD-17 | 2026-09-27 | No second LLM provider unless justified by the assessment or an identified compatibility requirement | **Owner** | P-005 §2 | A-04 remains an open risk |
| OD-18 | 2026-09-27 | Architecture approved: Python 3.12 + CLI contract; native GenAI SDK; controlled tool calling; full-context grounding; stateless per-case execution; shared immutable resources; read-only user-scoped tools; structured outputs + programmatic validation; safe escalation + inference limits; no unnecessary frameworks/vector DBs/infrastructure | **Owner** | P-005 §3 | — |
| OD-19 | 2026-09-27 | Owner manages and validates credentials locally; caching is not a functional prerequisite; A-10 corrected with the original observation preserved | **Owner** | P-005 §1 | `docs/reviews/credential-provenance-2026-09-27.md` |
| OD-20 | 2026-09-27 | Private GitHub repo, but **no remote creation or push** until the final confidentiality and credential checks pass; final submission also runnable as a ZIP | **Owner** | P-005 §5 | Gate: readiness §F |
| OD-21 | 2026-09-27 | Agents: Orchestrator coordinator; one primary implementer; one independent evaluation agent on separate files; Codex reviewer; Claude Cloud optional and off the critical path | **Owner** | P-005 §7 | Confirms OD-10 |
| OD-22 | 2026-09-27 | Deployment remains optional and after the mandatory deliverables; no infrastructure now | **Owner** | P-005 §8 | Confirms OD-11 |
| OD-23 | 2026-09-27 | Do not launch IP-01/E-01 or begin implementation until explicit owner authorization | **Owner** | P-005 §10 | Lifted by P-006 |
| OD-24 | 2026-09-27 | Implementation authorized (IP-01/E-01 onward); real runs only on a verified project | **Owner** | P-006 | — |
| OD-25 | 2026-09-28 | Billing verified: `GOOGLE_API_KEY` project is on the paid tier (prepaid); first real evaluation authorized; publication/deploy still need separate authorization | **Owner** | P-007 | Resolves A-10; unblocks T-13 |

## OD-26 — Free inference provider for the assessment (owner-approved, 2026-09-28, P-008)

Supplementary record: this does not belong in the three graded ADRs, though ADR-3 references it.

- **Decision (owner):** investigate and adopt a compatible free inference provider. Research recommendation: **GroqCloud free plan**, primary `openai/gpt-oss-120b`, fallback `openai/gpt-oss-20b` (same org and key, so the same data terms). Zero Data Retention should be enabled in Groq Data Controls.
- **Budget constraint:** the owner's available budget for paid inference.
- **Observed Gemini availability failures:** runs 001–003 (`ITERATION.md` §1). Synthetic probes showed provider-wide 503/504 on the paid standard tier across Flash and Flash-Lite models. 21–30 of 35 cases ended in safe failure.
- **Alternatives considered** (`docs/planning/research/free-provider-report.md`):
  - Paid: stay on Gemini paid (unavailable during the incident); a larger or other paid model (budget).
  - Free: **Groq free** — no training by contract, no retention by default, ZDR available. **Cerebras trial** — best features, but $5 credits, a card and a 30-day expiry. **OpenRouter `:free`** — 50 requests/day, and some upstreams log or train. **Mistral free** — trains unless you opt out. **Google AI Studio free** — Unpaid terms: human review and training. **GitHub Models** — retired.
- **Groq capabilities:** tool calling; strict json_schema structured output; automatic prompt caching on gpt-oss; OpenAI-compatible API.
- **Groq limitations:**
  - json_schema can't be combined with tools, so the adapter uses a `submit_answer` function tool.
  - Free quotas are **8K TPM and 200K TPD per model**, which needs client-side pacing and spreading runs across both models. The quota, not RPM, is the binding limit.
  - Reasoning tokens count toward limits.
  - Cache hits are not guaranteed.
- **Privacy and confidentiality:**
  - The materials are synthetic, and SUBMISSION.md prohibits *public posting*, not provider processing.
  - Groq's terms forbid training on inputs/outputs; logs are kept up to 30 days for reliability/abuse unless ZDR is on.
  - **Accepted residual risk:** policy text and synthetic order data are processed by a third party under free-plan terms.
  - Only the minimum inference context is sent (system prefix, question, the caller's own tool results) — never credentials, repo contents or development logs.
- **Would reconsider if:** Groq's terms change (training or retention); ZDR is unavailable to the org and the owner rejects 30-day logs; the free quotas can't complete the evaluation runs; or gpt-oss quality on the eval sets is clearly below Gemini's valid-response behaviour.
- **Results after migration:** *to be filled with runs 004+* (do not pre-fill).
- **Implementation:** per P-006, Claude is the primary implementer. Claude hit its usage limit (96 %), so the adapter was implemented by **Codex** under the owner's cross-provider failover policy. Its independent review is assigned to Claude, keeping implementer ≠ reviewer.

## Agent recommendations — status after P-005

Written into the specs as `[AR-nn]`. Status values:
- **Provisionally approved (owner)** — explicitly named in P-005 §4.
- **Owner-directed** — superseded by an owner decision.
- **Consistent, not explicitly approved** — follows from approved direction (OD-18), applied as the default, and the owner may override at authorization.
- **Proposed** — new.

| # | Recommendation | Origin | Where | Status |
|---|---|---|---|---|
| AR-01 | ≤1 tool round; call #2 with tool mode `none` | Codex review (A-009) + lead | architecture §5 | Consistent, not explicitly approved ("controlled tool-calling", "appropriate inference limits", OD-18) |
| AR-02 | Route derived in code from escalation signal + actual tool execution + a model-emitted `policy_applied` flag (not citations) | Codex reviews A-009, R-00 | architecture §3.3, §6 | **Provisionally approved (owner)** — validate against official requirements, not visible cases |
| AR-03 | Typed-claim output validator (pass/warn/fail) instead of a global numeric firewall | Codex reviews A-009, R-00 | security §4 | **Provisionally approved (owner)** |
| AR-04 | Neutral facts only in the baseline; policy-conclusion facts only as measured iterations | Codex review, reconciled with OD-12 | architecture §4 | Consistent, not explicitly approved (OD-12, OD-18 "deterministic business invariants where appropriate") |
| AR-05 | Holdout adversarial set stored outside the repo until the final run | Lead | evaluation spec | Consistent, not explicitly approved (supports "don't overfit to visible cases") |
| AR-06 | Free-tier key never used as automatic fallback | Gemini research + smoke test | architecture §7, A-10 | **Owner-directed** → OD-16 |
| AR-07 | One-way escalation tripwire extended to explicit human-only action requests and explicit human requests (precision-first; never writes answers) | Codex review R-00 #7 | security §3, architecture §5 | **Provisionally approved (owner)** |
| AR-08 | Scope tiers and cut order | Codex review R-00 #12 | tasks.md | **Provisionally approved (owner)** |
| AR-09 | Application reads the key only from `GOOGLE_API_KEY` and passes it explicitly; an inherited `GEMINI_API_KEY` is ignored; runs record credential env-var name + fingerprint | Credential investigation (P-005 §1) | architecture §8, evaluation §6 | Proposed |

## Pending owner decisions
See `docs/readiness-checklist.md` §"Decisions requiring owner approval".
