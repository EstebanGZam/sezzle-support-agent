You are the INDEPENDENT REVIEWER (Codex; the code was written by Claude agents). READ-ONLY code review. Do NOT modify any file except your single output file docs/reviews/R-01.md. Do NOT read /home/esteban/Documents/Sezzle/holdout/. Do NOT read .env. No network, no real LLM calls. You may run `uv run pytest -q`, `uv run ruff check .`, and `LLM_PROVIDER=fake python3 run_cases.py cases/golden_visible.jsonl /tmp/r01/answers.jsonl` (mkdir /tmp/r01 first).

Execute **R-01 (T-12)** as written in docs/implementation-prompts.md. Review src/support_agent/**, run_cases.py, evals/score.py and tests/** against specs/requirements.md, specs/architecture.md, specs/security.md, specs/evaluation.md §5–§7 and DECISIONS.md ADR-1. Check at minimum:
1. SEZ-F01: no code path returns a substantive canned answer (only the SEC-10 safe-failure text); the tripwire never writes answers.
2. Authorization: user_id never model-controlled; caller filter before matching; foreign == nonexistent payloads; no write tools; fraud mode withholds the tool; rejected/extra tool calls never executed; model-supplied user_id ignored.
3. Loop bounds: ≤1 executed tool call, call #2 and repair use tool mode none, ≤3 semantic calls, attempts cap, batch limit, auth/billing circuit breaker writes all lines + exit 3.
4. Validator correctness vs security §4 (false positives/negatives you can demonstrate with a concrete string), escalation_coherence, fraud read-back.
5. Route derivation vs architecture §6 (policy_applied; forced_reason precedence).
6. Secrets: key only from GOOGLE_API_KEY, passed explicitly; inherited GEMINI_API_KEY ignored; nothing secret in traces/config/logs/errors.
7. Overfitting: golden/adversarial ids, questions or case-specific strings in src/ or prompts.
8. Prompt quality: does the system prompt (src/support_agent/prompts.py) clearly teach grounding, escalation-with-explanation, policy_applied semantics, domain restriction, untrusted-input handling — anything likely to cause obvious failures on the official brief?
9. Tests actually assert the acceptance criteria (not tautologies).
10. Anything that would break `python3 run_cases.py` for a reviewer on a clean machine.
For each finding: severity (BLOCKER/MAJOR/MINOR/NIT), file:line, concrete failing input/behaviour, suggested fix. End with "Top fixes before the first real evaluation run". ~800-1400 words.
