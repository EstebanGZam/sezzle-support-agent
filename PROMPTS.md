# PROMPTS.md

Required by the brief: "the prompts you used to build (including scaffolding asks) and the prompts inside your system". Exact texts are stored verbatim under `docs/planning/prompts/` and are linked here, not paraphrased. Each record gives: ID · purpose · tool/agent · exact prompt · context · expected · observed · files · commit · follow-up.

> Status: **pre-implementation**. Sections 3–4 fill in during the build. Prompts P-001…P-004 and A-000…A-011 predate the timed build; the owner manages assessment time (A-11).

## 1. Planning prompts (owner → lead)

| ID | Purpose | Agent | Exact prompt | Observed outcome | Follow-up |
|---|---|---|---|---|---|
| P-001 | Master advisory: requirements, research, SDD, orchestration, 20-section report | Claude Code lead (Opus 5.5) | `docs/planning/prompts/P-001-master-advisory-prompt.md` | `docs/planning/ADVISORY_REPORT.md`; 7 research teammates | Owner requested a stack comparison |
| P-002 | Same text as P-001, re-sent after an account `/login` | lead | identical to P-001 | Not re-run (avoided duplicate spend) | — |
| P-003 | Evidence-based stack comparison; owner keeps decision authority | lead | `docs/planning/prompts/P-003-stack-comparison-prompt.md` | `docs/planning/STACK_DECISION_MATRIX.md`; independent Codex review changed 6 recommendations | Owner approved direction (P-004) |
| P-004 | Owner-approved technical direction + authorization of the SDD preparation phase | lead | `docs/planning/prompts/P-004-owner-approved-direction.md` | This repository's specs, ADR drafts, eval design, prompts, checklist | Owner decisions pending (`docs/readiness-checklist.md`) |

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

## 3. System prompts (inside the assistant)
_To be recorded at implementation time: full text of the static system prefix and case template, with `PROMPT_VERSION` per change and the eval run that motivated each change._

## 4. Evaluation prompts & probes

| ID | Purpose | Target | Exact prompt | Observed |
|---|---|---|---|---|
| S-001 | Flash-Lite smoke test: function calling, JSON schema + tools, thought signatures, latency, caching probe. **Synthetic content only** (fictional store; no assessment material) | Gemini API (REST) | `docs/planning/smoke-test/smoke_flash_lite.py` | `docs/planning/smoke-test/results.json`: 3.5 & 3.1 Flash-Lite pass tools+schema; 2.5 Flash-Lite rejects the combination; explicit cache → 429 *free-tier limit 0* (key is on the free tier, A-10) |
