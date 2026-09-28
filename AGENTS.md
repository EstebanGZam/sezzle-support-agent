# AGENTS.md — rules for every coding agent in this repo

Single source of truth for agent instructions (Claude Code reads it via `CLAUDE.md` → `@AGENTS.md`; Codex reads it natively). Keep it short; details live in `specs/`.

## Project
LLM-powered shopper-support assistant for the Sezzle take-home. Contract: `python3 run_cases.py <cases.jsonl> <answers.jsonl>` → `{id, route, answer}`, route ∈ {policy, tool, both, escalate}. Official brief: `assessment/PROMPT.md`.

## Source-of-truth order (read before working)
1. `assessment/PROMPT.md`, `assessment/SUBMISSION.md`, `data/policies/`, `data/orders.json` — **official, never edit** (integrity: `sha256sum -c assessment/SHA256SUMS`).
2. `specs/requirements.md` (SEZ = Sezzle, OWN = owner-approved, SEC = security) and `specs/assumptions.md`.
3. `specs/architecture.md`, `specs/security.md`, `specs/evaluation.md`.
4. `specs/tasks.md` — your task, its files, and its acceptance criteria.
5. `DECISIONS.md` (3 graded ADRs) and `docs/decision-log.md` (owner decisions).

## Execution protocol (every task)
1. **Analyze:** read the task row + the referenced requirements; list anything ambiguous.
2. **Plan:** state your approach and the files you will touch (only the task's files).
3. **Implement:** the smallest change that meets the acceptance criteria.
4. **Test:** `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` (fake LLM; no network).
5. **Verify:** check each acceptance criterion explicitly; give evidence (test names, output).
6. **Report:** what was done, deviations from the spec, open issues. Never silently edit a spec to match your code; propose the change instead.
7. **Commit:** Conventional Commits 1.0.0 with the task ID, e.g. `feat(tools): scoped read-only order lookup [T-05]`. One logical change per commit; no fabricated history; never commit failing tests.

## Hard rules
- **Owner approval is required** for: new dependencies beyond `specs/tasks.md` T-01, changing a requirement/ADR, adding tools/capabilities, network/LLM calls with real keys, pushing to any remote.
- The LLM answers; code constrains (ADR-1). Do not write code that produces substantive policy/order answers without the model. The only canned text is the safe-failure message (SEC-10).
- **No overfitting:** never put golden/adversarial case IDs, questions, or case-specific strings in code or prompts. Do not tune to individual cases.
- **Never read `/home/esteban/Documents/Sezzle/holdout/`** (held-out eval set). Only the evaluation agent copies it in, for the final run.
- Tools are read-only and scoped by the harness `user_id` (closure). Never add a `user_id` tool parameter or any write-capable tool.
- Use the frozen `today` from `data/orders.json`, never the system clock.
- Secrets: keys only via env/`.env` (git-ignored). Never print, log, trace, or commit keys; never paste them into prompts or docs.
- Don't send assessment material to any external service other than the approved LLM provider, and only after billing is confirmed (`specs/assumptions.md` A-10).
- Work only in your assigned worktree/branch. One owner per file (see `specs/tasks.md`). Don't modify files owned by another task.
- Language: English for code, comments, docs, and commits.

## Commands
- Setup: `uv sync --locked`
- Lint/format: `uv run ruff check . && uv run ruff format --check .`
- Tests (offline): `uv run pytest -q`
- Real run (owner-authorized only): `uv run --env-file .env python run_cases.py cases/golden_visible.jsonl evals/runs/NNN_label/answers.jsonl`
- Score: `uv run python evals/score.py <cases.jsonl> <answers.jsonl> [--trace <trace.jsonl>]`
