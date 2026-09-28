Read AGENTS.md first and follow its execution protocol. Implement ONLY the task(s) named below, touching ONLY the listed files.
Before coding, state your plan and the requirement IDs you implement. When done, report: acceptance criteria with evidence,
verification output of the FULL gate `uv run ruff check . && uv run ruff format --check . && uv run pytest -q` (plus any task-specific command),
deviations from specs, open issues. Commit with a Conventional Commit message including the task ID.
Never read /home/esteban/Documents/Sezzle/holdout/. No real LLM calls unless the prompt says so.

TASK: execute **IP-04 — LLM protocol, fake, Gemini adapter (T-07, T-08)** exactly as written in docs/implementation-prompts.md.
Specs: specs/architecture.md §3.3 (final answer schema incl. policy_applied), §3.4 (LLMClient protocol), §7 (canonical error/retry/fallback table: semantic calls vs transport attempts; auth_billing circuit breaker), §8 (config incl. FAKE_LLM_SCRIPT and the default fake responder); docs/planning/smoke-test/ (tools + JSON schema combine on 3.x Flash-Lite; append the raw model turn unchanged so Gemini 3 thought signatures survive).
Files you own: src/support_agent/llm/base.py, src/support_agent/llm/fake.py, src/support_agent/llm/gemini.py, src/support_agent/llm/__init__.py (exports), tests/test_fake_llm.py, tests/test_gemini_errors.py (+ tests/test_gemini_live.py marked @pytest.mark.live, skipped by default).
Notes:
- Use Settings from config.py (do not modify it): api_key via Settings (Secret) → genai.Client(api_key=...) explicitly; never let the SDK read env vars itself; SDK HttpRetryOptions/automatic retries OFF (our loop owns retries); AutomaticFunctionCallingConfig(disable=True); thinking level from settings; tool mode 'auto' | 'none' mapped to FunctionCallingConfig; response_schema from a pydantic FinalAnswer model defined in llm/base.py (answer, escalation_reason enum incl. 'none', policy_applied, cited_policies) — the agent (T-10) will re-validate it.
- Normalized LLMResponse must expose usage {input, output, cached, thoughts} (cached from usage_metadata.cached_content_token_count; None-safe), model_id actually used, per-attempt records {model, status, error_class, latency_ms} for the trace, and raw_model_turn (opaque) for history.
- Error classification must be unit-tested with stubbed google.genai.errors (ClientError/ServerError with codes/statuses/messages) and stubbed timeouts — no network. Distinguish rate_limit_minute vs quota_daily from the error message/details (document the heuristic), model_not_found → fallback-eligible, auth_billing → raise a dedicated exception the agent/CLI will turn into the circuit breaker.
- Fallback uses the same Settings/credential; only the model id changes (OD-16).
- The live test (skipped by default) may, when explicitly run by the owner, send ONE synthetic non-assessment prompt; do not run it yourself.
