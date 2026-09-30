# PROMPTS.md

Required by the brief: "the prompts you used to build (including scaffolding asks) and the prompts inside your system". Exact texts are stored verbatim under `docs/planning/prompts/` and are linked here, not paraphrased. Each record gives: ID · purpose · tool/agent · exact prompt · context · expected · observed · files · commit · follow-up.

> Status: implementation and evaluation phases logged below; see `ITERATION.md` for run outcomes. Prompts P-001…P-004 and A-000…A-011 predate the timed build; the owner manages assessment time (A-11).

## 1. Planning prompts (owner → lead)

| ID | Purpose | Agent | Exact prompt | Observed outcome | Follow-up |
|---|---|---|---|---|---|
| P-001 | Master advisory: requirements, research, SDD, orchestration, 20-section report | Claude Code lead (Opus 5.5) | `docs/planning/prompts/P-001-master-advisory-prompt.md` | advisory report (internal, written in Spanish at the owner's request; kept in the repository but excluded from the submission archive) and 7 research teammates (`docs/planning/research/`) | Owner requested a stack comparison |
| P-002 | Same text as P-001, re-sent after an account `/login` | lead | identical to P-001 | Not re-run (avoided duplicate spend) | — |
| P-003 | Evidence-based stack comparison; owner keeps decision authority | lead | `docs/planning/prompts/P-003-stack-comparison-prompt.md` | `docs/planning/STACK_DECISION_MATRIX.md`; independent Codex review changed 6 recommendations | Owner approved direction (P-004) |
| P-004 | Owner-approved technical direction + authorization of the SDD preparation phase | lead | `docs/planning/prompts/P-004-owner-approved-direction.md` | This repository's specs, ADR drafts, eval design, prompts, checklist | Owner decisions (P-005) |
| P-005 | Owner decisions: model config, architecture approval, AR reconciliation, Gemini credential-provenance investigation, remote-repo gate | lead | `docs/planning/prompts/P-005-owner-final-preparation-decisions.md` | Credential investigation (`docs/reviews/credential-provenance.md`); A-10 revised (original preserved); OD-15…OD-23; AR statuses; final readiness checklist | Implementation authorized (P-006) |
| P-006 | Implementation authorization (IP-01 + E-01 onward), execution methodology, credential and publication boundaries | lead | `docs/planning/prompts/P-006-implementation-authorization.md` | Implementation started; real LLM runs gated on owner confirmation of the credential project's data-handling terms | — |
| P-007 | Billing confirmation (paid tier, prepaid) and authorization of the first real evaluation | lead | `docs/planning/prompts/P-007-billing-confirmation.md` | A-10 resolved; baseline run 001 unblocked | — |
| P-008 | Owner decision: adopt a free inference provider (Groq investigated first) | lead | `docs/planning/prompts/P-008-free-provider-decision.md` | Research A-028; Groq adapter; OD-26 | — |
| P-009 | Groq key configured + ZDR enabled | lead | `docs/planning/prompts/P-009-groq-key-zdr-confirmation.md` | Live smoke + run 004 on Groq | — |

## 2. Development-agent prompts (lead → teammates)

| ID | Purpose | Agent / provider | Exact prompt | Observed outcome | Files |
|---|---|---|---|---|---|
| A-000 | Shared research brief appended to research dispatches | — | `docs/planning/prompts/agents/A-000-shared-research-brief.md` | Constraints followed; outputs secret-scanned | — |
| A-001…A-007 | Brand, Claude Cloud, Gemini, deployment, SDD/tooling, security review, requirements analysis | claude (headless via orchestrator) | `docs/planning/prompts/agents/A-001-to-A-007-phase1-research-dispatches.md` | 7 reports | `docs/planning/research/*` |
| A-008 | Stack fact check (Spring AI, Pydantic AI, LiteLLM, OpenAI-compat, caching, async, Python) | claude | `docs/planning/prompts/agents/A-008-stack-researcher.task.md` | Found the caching-minimum gap | `docs/planning/research/stack-report.md` |
| A-009 | Skeptical architecture review (cross-provider) | codex | `docs/planning/prompts/agents/A-009-architecture-challenger.task.md` (+ context summary) | 1st attempt failed (Codex needs a git cwd; config issue, not quota) → re-dispatched; 6 changes adopted | `docs/planning/research/architecture-challenge-review.md` |
| A-010 | Evaluation design + vetting/splitting adversarial cases (dev in repo, holdout outside) | claude | `docs/planning/prompts/agents/A-010-eval-designer.task.md` | 25 dev + 15 holdout cases; 19 draft cases kept/fixed, 10 dropped/merged | `specs/evaluation.md`, `cases/adversarial_dev.jsonl` |
| A-011 | Independent review of the SDD preparation package | codex | `docs/planning/prompts/agents/A-011-spec-package-review.task.md` | Verdict "not ready": 1 blocker, 11 major, 1 minor → all resolved or escalated to owner (`docs/reviews/R-00-resolution.md`) | `docs/reviews/R-00-spec-package.md` |
| A-012 | Apply review fixes to evaluation-owned files (holdout leak, canonical trace, dev regexes) | claude | `docs/planning/prompts/agents/A-012-eval-fixes.task.md` | see `specs/evaluation.md` changelog | `specs/evaluation.md`, `cases/adversarial_dev.jsonl`, holdout (outside repo) |
| IP-01… | Implementation prompts (to be dispatched after authorization) | per `docs/implementation-prompts.md` | as sent, logged here at dispatch time | — | — |

### Build-phase dispatches (exact text in the linked files)
| ID | Purpose | Exact prompt |
|---|---|---|
| A-013 | IP-01 scaffold + config | `docs/planning/prompts/agents/A-013-impl-IP-01.task.md` |
| A-014 | E-01 scorer (evaluation agent; ran on Codex) | `docs/planning/prompts/agents/A-014-eval-E-01.task.md` |
| A-015 | IP-02/IP-03 resources, facts, scoped tool | `docs/planning/prompts/agents/A-015-impl-IP-02-IP-03.task.md` |
| A-016 | Recovery handoff IP-02/03 (Claude limit) | `docs/planning/prompts/agents/A-016-impl-recovery-IP-02-IP-03.task.md` |
| A-017 | IP-04 LLM protocol, fake, Gemini adapter | `docs/planning/prompts/agents/A-017-impl-IP-04.task.md` |
| A-018 | IP-05 prompts + guards | `docs/planning/prompts/agents/A-018-impl-IP-05.task.md` |
| A-019 | Recovery handoff IP-05 (session limit) | `docs/planning/prompts/agents/A-019-impl-recovery-IP-05.task.md` |
| A-020 | IP-06 agent loop, routing, trace, CLI | `docs/planning/prompts/agents/A-020-impl-IP-06.task.md` |
| A-021 | Fix: Gemini 10 s minimum deadline (found by live smoke) | `docs/planning/prompts/agents/A-021-impl-fix-timeout.task.md` |
| A-022 | Codex review R-01 | `docs/planning/prompts/agents/A-022-review-R-01.task.md` |
| A-023 | Fix R-01 findings 1-4,6 | `docs/planning/prompts/agents/A-023-impl-fix-R-01.task.md` |
| A-024 | Fix R-01 finding 5 (scorer labels) | `docs/planning/prompts/agents/A-024-evals-fix-R-01.task.md` |
| A-025 | Recovery handoff R-01 impl fixes | `docs/planning/prompts/agents/A-025-impl-recovery-R-01.task.md` |
| A-026 | Recovery handoff R-01 eval fixes | `docs/planning/prompts/agents/A-026-evals-recovery-R-01.task.md` |
| A-027 | Iteration 1: overload failover + primary cooldown | `docs/planning/prompts/agents/A-027-impl-iter1-resilience.task.md` |
| A-028 | Free-provider research | `docs/planning/prompts/agents/A-028-free-provider-research.task.md` |
| A-029 | Iteration 2: system prompt v2 | `docs/planning/prompts/agents/A-029-impl-iter2-prompt-v2.task.md` |
| A-030 | Groq adapter | `docs/planning/prompts/agents/A-030-impl-groq-adapter.task.md` |
| A-031 | Failover handoff Groq adapter (Codex limit) | `docs/planning/prompts/agents/A-031-impl-groq-adapter-failover.task.md` |
| A-032 | Codex review R-02 (Groq) | `docs/planning/prompts/agents/A-032-review-R-02-groq.task.md` |
| A-033 | Fix: Groq tool_use_failed recovery | `docs/planning/prompts/agents/A-033-impl-groq-tool-use-failed.task.md` |
| A-034 | Fix: Groq 413 classification + provider error detail | `docs/planning/prompts/agents/A-034-impl-groq-413-observability.task.md` |
| A-035 | Fix: Groq output_parse_failed recovery | `docs/planning/prompts/agents/A-035-impl-groq-output-parse-failed.task.md` |
| A-036 | Fix R-02 findings 1,2,4 | `docs/planning/prompts/agents/A-036-impl-fix-R-02.task.md` |

## 3. System prompts (inside the assistant)

**Structure:**
- The **system instruction** is a static prefix, byte-identical for every case: the instructions below, then all 12 policies rendered as `[POL-NN] <title>` + text from `data/policies/`. See `src/support_agent/prompts.py` → `build_system_prompt`.
- The **per-case user turn** comes from `build_case_message`: `Today is <frozen date>.`, plus an optional one-way tripwire note. The shopper's text goes inside `<shopper_message>…</shopper_message>` and is declared untrusted data. Tag look-alikes inside the text are neutralised.
- **Tool declaration** (`get_my_orders`, read-only, no user field) and the **final-answer schema** (`FinalAnswer`: `answer`, `escalation_reason`, `policy_applied`, `cited_policies`) are sent as structured tool/schema definitions.
  - Gemini: `response_schema`.
  - Groq: a `submit_answer` function.
- `PROMPT_VERSION` = sha256 of prefix + tool declarations + answer schema (16 hex chars). It is recorded in every run's `config.json`.

| Version | Instruction text (verbatim) | `PROMPT_VERSION` | Used in runs | Motivated by |
|---|---|---|---|---|
| v1 | `docs/system-prompts/v1-instructions.txt` | `3103d85377df1a31` | 001–004 | Initial spec (T-06): scope, grounding, escalation guidance, voice, output contract |
| v2 | `docs/system-prompts/v2-instructions.txt` | `e1143a2c8857656f` | 005+ | Iteration 2: behaviour failures on valid answers in runs 003/004. Rules added for decision boundaries (no escalation when policy gives a definitive answer; no tool use for hypotheticals; injection doesn't block a legitimate lookup), policy consequences, and explicit hand-off. The generation prompt is A-029 |

The diff between v1 and v2 is `git diff --no-index docs/system-prompts/v1-instructions.txt docs/system-prompts/v2-instructions.txt`.

## 4. Evaluation prompts & probes

| ID | Purpose | Target | Exact prompt | Observed |
|---|---|---|---|---|
| S-001 | Flash-Lite smoke test: function calling, JSON schema + tools, thought signatures, latency, caching probe. **Synthetic content only** (fictional store; no assessment material) | Gemini API (REST) | `docs/planning/smoke-test/smoke_flash_lite.py` | `docs/planning/smoke-test/results.json`: 3.5 & 3.1 Flash-Lite pass tools+schema; 2.5 Flash-Lite rejects the combination; explicit cache → 429 *free-tier cache-storage limit 0*. **Original interpretation** ("key is on the free tier") was **revised** in P-005: inference available; billing unverified; cache quota ≠ inference (A-10 revised). Credential used: inherited `GEMINI_API_KEY`, fingerprint `53408af16a25` |
