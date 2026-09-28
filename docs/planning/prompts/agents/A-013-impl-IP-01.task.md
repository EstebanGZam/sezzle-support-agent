Read AGENTS.md first and follow its execution protocol. Implement ONLY the task(s) named below, touching ONLY the listed files.
Before coding, state your plan and the requirement IDs you implement. When done, report: acceptance criteria with evidence,
verification output of the FULL gate `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` (plus any task-specific command),
deviations from specs, open issues. Commit with a Conventional Commit message including the task ID.
Never read /home/esteban/Documents/Sezzle/holdout/. No real LLM calls unless the prompt says so.

TASK: execute **IP-01 — Scaffold + config (T-01, T-02)** exactly as written in docs/implementation-prompts.md, using specs/tasks.md rows T-01/T-02 and specs/architecture.md §2 and §8 (config defaults: gemini-3.5-flash-lite primary, gemini-3.1-flash-lite fallback; GOOGLE_API_KEY is the ONLY key source — an inherited GEMINI_API_KEY must be ignored; credential_fingerprint = first 12 hex of SHA-256; known-compatible model set with explicit override; repr never shows the key).
Notes:
- You are in a git worktree of the repo; .env is git-ignored and NOT present here — do not create one, do not read any .env, never print keys.
- `uv` will provision Python 3.12 (`requires-python = ">=3.12,<3.13"`); dependencies exactly as T-01 lists (runtime: google-genai>=2.25,<3, pydantic>=2,<3; dev group: pytest, ruff). Also produce requirements.txt via `uv export --no-dev --no-hashes -o requirements.txt`.
- Put ruff config in pyproject.toml (line-length 100, target py312). Add `[tool.pytest.ini_options]` with `markers = ["live: real LLM calls, skipped by default"]` and `addopts = "-m 'not live'"`.
- Commit(s) on your branch; do not merge. One commit for T-01 (build), one for T-02 (feat(config)).
