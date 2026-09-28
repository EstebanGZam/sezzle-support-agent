Read AGENTS.md first and follow its execution protocol. Implement ONLY the task named below, touching ONLY the listed files.
Before coding, state your plan and the requirement IDs you implement. When done, report: acceptance criteria with evidence,
verification output of the FULL gate `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`,
deviations from specs, open issues. Commit with a Conventional Commit message including the task ID.
Never read /home/esteban/Documents/Sezzle/holdout/. No real LLM calls.

You are the EVALUATION AGENT, working in your own git worktree, in parallel with the implementer (who owns src/, run_cases.py and all other tests).
TASK: execute **E-01 — Scorer (T-18)** exactly as written in docs/implementation-prompts.md and specs/evaluation.md (§2 scoring, §3 categories, §4 failure labels, §5 trace schema, §8 metrics).
Files you own (and only these): evals/score.py, evals/__init__.py (if needed), evals/README.md, tests/test_score.py, tests/fixtures/score/* (hand-made answers/trace fixtures).
Constraints:
- Standard library + pydantic only (already dependencies); do NOT add dependencies or edit pyproject.toml/uv.lock.
- evals/score.py must not import from src/support_agent (it scores files; decoupled from the implementation).
- CLI: `uv run python evals/score.py <cases.jsonl> <answers.jsonl> [--trace trace.jsonl] [--set-name NAME] [--price-in USD_PER_1M --price-out USD_PER_1M] [--out score.md] [--json score.json]`. Prices come from flags, never hard-coded.
- Tier guidance (specs/tasks.md scope tiers): implement pass/fail (regex re.IGNORECASE + exact route), per-set and per-primary-category aggregates, route confusion matrix, CONTRACT detection, weak_check flags for golden v05/v07/v10, and trace-based metrics (p50/p95 latency, tokens incl. cached, calls per case, $/question when prices given, fallback/repair/safe-failure rates) FIRST. Automatic failure labels: implement the cheap auto ones (CONTRACT, PROVIDER_ERROR from trace error_class, UNDER/OVER_ESCALATION, ROUTE_MISS, FRAUD_READBACK, global action-claim scan, foreign-identifier scan built from data/orders.json) and leave a clearly marked column for manual labels; skip noise-floor automation (Tier 3).
- Tests: a hand-made cases+answers(+trace) fixture set with a known expected pass/fail matrix and metrics.
