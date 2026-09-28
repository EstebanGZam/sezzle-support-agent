# Sezzle Support Agent (take-home)

> **Status: specification complete, implementation not started.** This README becomes the half-page run guide + honest "unfinished" note at delivery (task T-16).

An LLM-powered shopper-support assistant that answers policy questions, looks up the shopper's own orders through a scoped read-only tool, and escalates what it shouldn't touch. Official brief: `assessment/PROMPT.md`.

## Where things are
- **Contract:** `python3 run_cases.py <cases.jsonl> <answers.jsonl>` (to be implemented).
- **Assessment materials:** `assessment/`, `data/`, `cases/golden_visible.jsonl`. Provenance: `assessment/MANIFEST.md`; verify with `sha256sum -c assessment/SHA256SUMS`.
- **Specs:** `specs/requirements.md`, `specs/assumptions.md`, `specs/architecture.md`, `specs/security.md`, `specs/evaluation.md`, `specs/tasks.md`.
- **Decisions:** `DECISIONS.md` (3 ADRs, proposed) · `docs/decision-log.md` (owner decisions).
- **Process:** `AGENTS.md` · `docs/agent-plan.md` · `docs/implementation-prompts.md` · `docs/readiness-checklist.md` · `PROMPTS.md`.
- **Planning evidence:** `docs/planning/` (advisory report, decision matrix, research, verbatim prompts, model smoke test).
