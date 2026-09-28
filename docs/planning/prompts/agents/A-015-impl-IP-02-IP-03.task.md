Read AGENTS.md first and follow its execution protocol. Implement ONLY the task(s) named below, touching ONLY the listed files.
Before coding, state your plan and the requirement IDs you implement. When done, report: acceptance criteria with evidence,
verification output of the FULL gate `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` (plus any task-specific command),
deviations from specs, open issues. Commit with a Conventional Commit message including the task ID.
Never read /home/esteban/Documents/Sezzle/holdout/. No real LLM calls unless the prompt says so.

TASKS (in order, one commit each): execute **IP-02 — Resources + neutral facts (T-03, T-04)** and then **IP-03 — Scoped read-only tool (T-05)** exactly as written in docs/implementation-prompts.md.
Specs: specs/architecture.md §2, §3.2, §4 (neutral facts only — AR-04; no eligibility/fee conclusions), specs/security.md §2 (LLM02), specs/requirements.md SEZ-F03, SEZ-F06, SEC-01..SEC-04, specs/assumptions.md A-05, A-06, A-07, A-13, A-14.
Files you own: src/support_agent/resources.py, src/support_agent/facts.py, src/support_agent/tools.py, tests/test_resources.py, tests/test_facts.py, tests/test_tools.py.
Notes:
- config.py already exists (IP-01): use Settings.data_dir; do not modify config.py.
- The tool declaration must be a plain JSON-schema dict usable later by the Gemini adapter (no google-genai imports in tools.py). The executor returns a JSON-serialisable dict; foreign and nonexistent order ids must produce byte-identical json.dumps(..., sort_keys=True) payloads.
- Do not hard-code users, orders, merchants or case strings in src/ — tests may reference data/orders.json facts (e.g. ord_3006 next upcoming = installment 4, 118.36, due 2026-07-11).
- Don't use the system clock anywhere; today comes from data/orders.json.
