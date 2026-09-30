Read AGENTS.md first and follow its execution protocol. Touch ONLY the listed files. Report ACs with evidence, full-gate output, deviations. Conventional Commit with task ID. Never read /home/esteban/Documents/Sezzle/holdout/ or .env. No real LLM/network calls.

FIX (T-08, provider integration — not a behaviour change). Evidence from run 004 (evals/runs/004_groq_prompt_v1) and a reproduction by the lead: Groq intermittently returns
HTTP 400 {"error":{"message":"Tool choice is required, but model did not call a tool","type":"invalid_request_error","code":"tool_use_failed","failed_generation":"{\n  \"answer\": \"…\",\n  \"cited_policies\": [],\n  \"escalation_reason\": \"none\",\n  \"policy_applied\": false\n}"}}
i.e. gpt-oss emitted the FinalAnswer JSON as text instead of calling submit_answer. In run 004 these surfaced as `bad_request` → SEC-10 safe failures (4 cases) even though the model's answer was present.
Required behaviour in src/support_agent/llm/groq.py:
1. Detect 400 with error.code == "tool_use_failed" (robust to missing fields).
2. If `failed_generation` parses as a JSON object that validates against FinalAnswer → return it as `final_json` (as if submit_answer had been called), flagging the attempt (e.g. trace attempt `recovered="tool_use_failed"`). Downstream validation/routing stay unchanged — do NOT bypass the agent's validator.
3. If it contains a get_my_orders-like call or anything else, or does not validate → return `malformed` so the agent's repair path runs (no same-model retry storm; count as one attempt). Never execute anything parsed from failed_generation as a tool call unless it is a well-formed get_my_orders call in tool mode `auto` — if you support that, it must go through the same validation as normal tool calls; otherwise treat as malformed. Prefer the simpler malformed path.
4. Never classify tool_use_failed as bad_request any more. Keep other 400s as bad_request.
5. Tests (httpx.MockTransport): the exact payload above → final_json with recovered flag; failed_generation with invalid/partial JSON → malformed; missing failed_generation → malformed; other 400 → bad_request; trace record shows the recovery.
Files you own: src/support_agent/llm/groq.py, tests/test_groq.py (and src/support_agent/llm/base.py only if AttemptRecord needs the optional `recovered` field — keep it absent from traces when unset).
Commit: fix(llm): recover Groq tool_use_failed answers from failed_generation [T-08]
