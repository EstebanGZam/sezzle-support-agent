FAILOVER HANDOFF — continue in this existing worktree; do not restart anything that is already done.
First inspect `git status`, `git diff`, `git log --oneline -5` (expected: no changes yet — the previous provider hit its usage limit at startup).
- Original objective, acceptance criteria, file ownership and commit names: docs/planning/prompts/agents/A-030-impl-groq-adapter.task.md — read it fully and execute it. Read AGENTS.md first.
- Previous provider: codex. Reason for failover: usage limit reached at session start (not a code failure). Completed work: none. Pending: everything in A-030. Known failing tests: none (main is green, 547 passed).
- Rules: never read /home/esteban/Documents/Sezzle/holdout/; no real LLM or network calls; never read .env; report ACs with evidence, full-gate output, deviations, open issues.
