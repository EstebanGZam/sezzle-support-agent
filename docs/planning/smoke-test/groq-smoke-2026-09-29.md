# S-002 — Groq synthetic smoke test (2026-09-29, fictional store; no assessment material)

Script: `groq_smoke.py`. Provider `groq`, primary `openai/gpt-oss-120b`, key fingerprint `e729a1ef031d` (`GROQ_API_KEY`; ZDR enabled by the owner, P-009).

| Call | Mode | Result | Latency | Usage (in/out/cached/reasoning) |
|---|---|---|---|---|
| 1 | tools `[get_my_orders, submit_answer]`, `tool_choice=required` | `get_my_orders({"order_id":"X-100"})` | 0.54 s | 396 / 39 / 0 / 8 |
| 2 | `submit_answer` forced, after the tool result | valid `FinalAnswer` JSON, grounded date, `policy_applied=true` | 0.73 s | 439 / 174 / 0 / 50 |

Confirms the two open issues from the adapter work:
- `include_reasoning=false` is accepted.
- Replaying the assistant tool-call turn plus the tool result is accepted.

Note: the synthetic prompt had no `POL-NN` IDs, so the model cited policy text. The real prompt defines IDs, and the validator drops unknown ones.
