Read AGENTS.md first and follow its execution protocol. Touch ONLY the listed files. Report ACs with evidence, full-gate output, deviations. Conventional Commit with task ID. Never read /home/esteban/Documents/Sezzle/holdout/. No real LLM calls.

TASK (fix, T-02/T-08): a live synthetic smoke call (run by the lead) failed with
`HTTP 400 INVALID_ARGUMENT: Manually set deadline 8s is too short. Minimum allowed deadline is 10s.`
The Gemini API enforces a server-side minimum request deadline of 10 s, but specs/architecture.md §8 set LLM_TIMEOUT_S default 8.
Fix:
1. config.py: default LLM_TIMEOUT_S = 10; enforce a minimum of 10 s for provider gemini — a lower configured value is raised to 10 and a message is appended to Settings.warnings (do not fail; the owner's local .env may contain 8).
2. llm/gemini.py: make sure the HttpOptions timeout passed to the SDK is never below the minimum (defensive), and keep the per-case deadline logic consistent with it.
3. Tests: config test for default 10 and clamp+warning; adapter test asserting the timeout handed to the SDK client is >= 10 s (stubbed, no network).
Files you own: src/support_agent/config.py, src/support_agent/llm/gemini.py, tests/test_config.py, tests/test_gemini_errors.py.
Commit as: fix(llm): respect Gemini 10 s minimum request deadline [T-02][T-08]
