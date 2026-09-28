RECOVERY HANDOFF — continue the existing implementation; do NOT restart from scratch.

First inspect `git status`, `git diff`, `git log --oneline -5`, the changed/untracked files and the existing tests in this worktree. Preserve correct partial work. Determine what is complete and what remains, then continue from the current repository state until the original acceptance criteria pass.

- Original objective: execute IP-02 (T-03 resources.py + T-04 facts.py) and then IP-03 (T-05 tools.py) exactly as written in docs/implementation-prompts.md; follow AGENTS.md (read it first) and the original task text in docs/planning/prompts/agents/A-015-impl-IP-02-IP-03.task.md (same file ownership and notes apply).
- Acceptance criteria: those listed for IP-02 and IP-03 in docs/implementation-prompts.md and specs/tasks.md (T-03, T-04, T-05), plus the FULL gate `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`.
- Previous provider: claude (previous Claude account). Reason for failover: the previous teammate process exited with rc=1 mid-task, consistent with usage-quota exhaustion on the previous account (not a code/test failure).
- Completed work (uncommitted, untracked): src/support_agent/resources.py, src/support_agent/facts.py, tests/test_resources.py, tests/test_facts.py; the suite passed (69 tests) at handoff time. Verify these against the IP-02 acceptance criteria before committing them.
- Pending work: verify/finish IP-02 and commit it (one Conventional Commit, [T-03][T-04]); implement IP-03 (src/support_agent/tools.py, tests/test_tools.py) and commit it ([T-05]).
- Known failing tests: none at handoff. Test command: the full gate above.
- Rules: never read /home/esteban/Documents/Sezzle/holdout/; no real LLM calls; no .env access; do not modify config.py or files outside the listed ownership. Report ACs with evidence, gate output, deviations, open issues.
