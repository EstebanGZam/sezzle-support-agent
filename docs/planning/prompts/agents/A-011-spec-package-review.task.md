You are an INDEPENDENT, skeptical reviewer (Codex; different provider from the spec author). READ-ONLY review of the SDD preparation package in this repository. Do NOT modify any file except your single output file docs/reviews/R-00-spec-package.md. Do NOT read /home/esteban/Documents/Sezzle/holdout/. No code, no installs, no network.

Read: AGENTS.md, CLAUDE.md, assessment/PROMPT.md, assessment/SUBMISSION.md, data/policies/*, data/orders.json, cases/golden_visible.jsonl, cases/adversarial_dev.jsonl, specs/*.md, DECISIONS.md, docs/decision-log.md, docs/agent-plan.md, docs/implementation-prompts.md, docs/readiness-checklist.md, PROMPTS.md.

Check and report findings with severity (BLOCKER/MAJOR/MINOR), file:section, and a concrete fix:
1. Consistency: contradictions between specs (IDs, task numbers, file ownership, config defaults, route rules, validator checks) and broken cross-references.
2. Traceability: every SEZ-* requirement has a task + verification; every task maps to requirements; missing Sezzle requirements vs assessment/PROMPT.md.
3. Provenance discipline: are owner choices (OWN/OD) ever presented as Sezzle requirements, or agent recommendations presented as owner-approved?
4. ADR format: DECISIONS.md has exactly 3 records, each <= ~10 lines with decision / options / why / evidence-that-would-change-my-mind; any claims presented as measured that are not.
5. The LLM-vs-deterministic line (PROMPT.md 'The LLM is the assignment' + owner clarification in docs/planning/prompts/P-004): does anything in architecture/security (tripwire, facts, validator, safe failure, route derivation) risk code answering instead of the model? Anything overfit to golden cases?
6. Security spec: gaps vs hostile inputs named in PROMPT.md (foreign/nonexistent orders, fee-waiver demands, ignore-your-rules); validator false-positive/false-negative risks; fraud mode; isolation.
7. Evaluation spec + adversarial_dev cases: wrong expected labels/regexes vs actual policy text and order data (spot-check at least 8 cases), trivially satisfiable or unfair regexes, leakage risk of holdout.
8. Implementation prompts: are they short, sequential, executable, with testable acceptance criteria and correct dependencies? Anything an implementer would have to guess?
9. Feasibility within ~2 hours: what should be cut first if time runs short?
End with 'Top 7 fixes before implementation'. ~900-1400 words.
