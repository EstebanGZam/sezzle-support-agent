# Run 004 — provider migrated to Groq (OD-26), prompt v1 unchanged (preserved unedited)

- **Isolates the provider change.** The code is main after the Groq adapter landed, with the same system prompt as runs 001–003 (`PROMPT_VERSION` in `config.json`).
- **Provider:** Groq free plan, ZDR enabled (P-009). `openai/gpt-oss-120b` primary, `openai/gpt-oss-20b` fallback, `reasoning_effort=low`.
- **Command overrides:** `LLM_PROVIDER=groq CASE_DEADLINE_S=180 LLM_MAX_ATTEMPTS=3 LLM_TIMEOUT_S=30 LLM_MAX_OUTPUT_TOKENS=1024`.
- **Cost:** $0 (free plan). The scorer was run with prices 0.

| Set | Case pass | Regex pass | Route acc. | Safe failures | Per-attempt service latency p50 / p95 |
|---|---|---|---|---|---|
| golden | **6/10** (003: 3/10) | 6/10 | **9/10** | 1 | 0.84 s / 1.35 s |
| adversarial_dev | **12/25** (003: 5/25) | 15/25 | 16/25 | 5 | 0.84 s / 1.26 s |

- **End-to-end case latency is dominated by client-side pacing** for the 8K TPM free quota (golden: 350 s of total waits). It does not reflect service latency.
- **Mean input** ≈ 4.4k tokens/case. Cached-token ratio: 0.13 (golden), 0.46 (dev).

## Diagnosis
- **Infrastructure/adapter (4 cases, `bad_request`):** reproduced. Groq returns `400 tool_use_failed` when gpt-oss emits the FinalAnswer JSON as text instead of calling `submit_answer`; the valid answer is in `failed_generation`. The adapter's detection didn't fire, so these became safe failures. This is fixed in the adapter; it is not a reasoning failure.
- **validation_exhausted (2):** the validator rejected the answer twice (escalation without an affirmative hand-off; schema).
- **Behaviour failures on valid answers:**
  - GROUNDING_MISS: v05 hand-off wording, v06 missing "90 days", v10 missing the unpaid-installments rule, d11, d12.
  - ROUTE_MISS: the tool wasn't called for the shopper's own order in d05/d07/d08/d14.
  - OVER_ESCALATION: d10, d16.

  These are the same classes observed on Gemini's valid answers in run 003, and they are addressed by prompt v2 (iteration 2).
