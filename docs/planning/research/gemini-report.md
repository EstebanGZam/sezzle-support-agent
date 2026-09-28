# Gemini as LLM provider — research report (2026-09-27)

Sources fetched today. **V** = verified on the cited official page; **U** = unverified, or my own assumption.
Heads-up: the ai.google.dev *guides* now describe the new **Interactions API** (`tool_choice`, `response_format`, lowercase error codes). The **generateContent** REST reference and the `google-genai` SDK still use `FunctionCallingConfig(mode=AUTO|ANY|NONE|VALIDATED, allowed_function_names)`. **Build on `client.models.generate_content`.** It is the stable, well-documented path.

## 1. Models, prices, availability

Sources: [pricing](https://ai.google.dev/gemini-api/docs/pricing) (last updated 2026-09-24), [models](https://ai.google.dev/gemini-api/docs/models) (2026-09-24), and one `models.list` call with the env key (HTTP 200; every ID below is listed, **V**).

| Model ID (stable) | In / Out per 1M | Cached input + storage | Free tier | Notes |
|---|---|---|---|---|
| `gemini-3.1-flash-lite` (05-2026) | $0.25 / $1.50 | $0.025 + $1.00/1M/hr | Yes | Cheapest current-gen text model that has a listed caching price |
| `gemini-3.5-flash-lite` (07-2026) | $0.30 / $2.50 | **"Not available"** on the pricing page, but the model page ticks "Caching ✓" (**conflict, U**) | Yes | Thinking defaults to `minimal`. Google recommends it for new projects |
| `gemini-3.8-flash` (09-2026) | $0.75 / $3.75 until 2026-12-31, then **$1.50 / $7.50** | $0.075 (→$0.15) + $0.50/hr | Yes | Thinking levels low, medium (default) and high only. "minimal is not supported" |
| `gemini-3.5-flash` | $1.50 / $9.00 | $0.15 | Yes | Too expensive for this use |
| `gemini-3.1-pro-preview` | $2 / $12 | $0.20 | **No** | Preview only, so not a fit |
| `gemini-2.5-flash-lite` | $0.10 / $0.40 | $0.01 | Yes | Legacy: "limiting access to users who have actively used them in the past" (**V**). Don't depend on it |

- **Aliases:** `gemini-flash-latest`, `gemini-flash-lite-latest` and `gemini-pro-latest` also exist (**V**, models.list). Pin explicit IDs so eval runs are reproducible.
- **Capabilities:** 3.1 Flash-Lite, 3.5 Flash-Lite and 3.8 Flash all support function calling, structured outputs, caching and thinking, with 1,048,576 input and 65,536 output tokens (**V**, each model page).
- **Free vs paid rate limits:** the [rate-limits page](https://ai.google.dev/gemini-api/docs/rate-limits) (2026-09-02) no longer publishes numbers. It says limits "can be viewed in Google AI Studio".
  - Limits are **per project, not per API key**. RPD resets at midnight Pacific.
  - **Tier 1** requires "set up and link an active billing account" ($250 billing-tier cap). The upgrade "typically takes effect instantly". **V**
  - **Per-model free and Tier 1 RPM/RPD/TPM: not officially published → U.** Third-party blogs claim about 15 RPM and 500–1,000 RPD for free Flash-Lite, but they contradict each other ([example](https://tinkerllm.com/blog/gemini-api-free-tier-limits-rate-quotas/)). Check the AI Studio rate-limit screen for the actual project.
  - `models.list` succeeding does **not** prove a model has non-zero quota, or show whether the key's project has billing.

## 2. Capabilities that matter for the agent

- **Function calling.** Source: [ToolConfig reference](https://ai.google.dev/api/caching#ToolConfig), **V**.
  - `AUTO` (default): the model chooses between a call and text.
  - `ANY`: "constrained to always predicting a function call".
  - `NONE`: no calls.
  - `VALIDATED`: like AUTO, but function calls are validated with constrained decoding.
  - `allowedFunctionNames` "limits the functions the model will call".
  - Parallel and compositional calls are supported ([guide](https://ai.google.dev/gemini-api/docs/function-calling)).
  - **Structural lever for the ADR:** register only the tools the authenticated `user_id` may use, and scope every tool to the session's `user_id` server-side. The model never supplies the user ID. Use `VALIDATED` so arguments match the schema.
- **SDK automatic function calling.** It runs when Python callables are passed as tools. **Disable it** with `AutomaticFunctionCallingConfig(disable=True)` and run your own loop, so each tool call is authorised, logged and capped (**V**, [python-genai README](https://github.com/googleapis/python-genai)).
- **Thought signatures (Gemini 3).** These must be sent back in history on function-call turns. The error taxonomy includes `missing_thought_signature` (**V**, [api-errors](https://ai.google.dev/gemini-api/docs/api-errors)). Fix: append `response.candidates[0].content` to history unchanged.
- **Structured output.** Set `response_mime_type="application/json"` plus a schema (Pydantic supported).
  - Combining with tools: "Gemini 3 lets you combine Structured Outputs with … Function Calling" (**V**, [structured-output](https://ai.google.dev/gemini-api/docs/structured-output), 2026-09-23). This is Gemini 3 series only, and 2.5 is excluded.
  - This allows a final `{route, answer, cited_docs}` object in the same loop.
- **Thinking.** Source: [thinking](https://ai.google.dev/gemini-api/docs/thinking), 2026-09-25.
  - Levels are `minimal | low | medium | high`. Thinking can't be fully disabled on Gemini 3.
  - Thinking tokens are **billed at the output rate** (**V**).
  - No official latency figures (**U**). Expect `minimal`/`low` to add little, and `medium` (3.8 Flash's default) to add seconds and output cost.
  - → Use `minimal` on Flash-Lite and `low` on 3.8 Flash.
- **Caching.** Source: [caching](https://ai.google.dev/gemini-api/docs/caching), 2026-09-02.
  - Implicit caching is on by default for 2.5+ models.
  - The minimum prefix is **4,096 tokens** for 3.x Flash and 3.1 Pro, and 2,048 for 2.5.
  - **Flash-Lite minimums are not listed (U).** Our prefix (about 3.3k tokens) is *below* the 3.x Flash threshold, so implicit hits on 3.8 Flash are unlikely unless the prefix is padded or grown.
  - Explicit caches are priced on the pricing page (storage for a 3.3k prefix ≈ $0.08/day, negligible). The minimum size for explicit caches is not stated (**U**).

## 3. `google-genai` Python SDK

- **Package:** `google-genai` **2.25.0**, `requires_python >=3.10`, classifiers 3.10–3.14 (**V**, [PyPI JSON](https://pypi.org/pypi/google-genai/json)).
- **API key:** the SDK reads `GEMINI_API_KEY` or `GOOGLE_API_KEY`. If both are set, **GOOGLE_API_KEY wins** (**V**, README). The environment currently has `GEMINI_API_KEY`, so pass the key explicitly to avoid surprises.
- **Retries are off by default.** `retry_options=None` → "never retry" (**V**, `_api_client.py`).
  - Opt in with `HttpOptions(retry_options=HttpRetryOptions(attempts=…, initial_delay=…, max_delay=…, http_status_codes=…))`.
  - The built-in retry defaults are 5 attempts, 1s initial delay, 60s max delay, retrying on 408/429/500/502/503/504. **That is incompatible with p95 ≤ 3s**, so set a tight policy: 2 attempts, `max_delay` 0.5s, plus `HttpOptions(timeout=…)`.
- **Errors:** `errors.APIError` has `.code` (HTTP) and `.status`. It is subclassed as `ClientError` (4xx) and `ServerError` (5xx) (**V**, `errors.py`).

## 4. Data-use terms (CRITICAL)

Source: [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms), last modified 2026-04-28, **V**.

- **Unpaid Services:** content is used "to provide, improve, and develop Google products". "Human reviewers may read, annotate, and process your API input and output". "**Do not submit sensitive, confidential, or personal information to the Unpaid Services.**" Data is disconnected from the account before review, and no retention period is stated.
- **Paid Services:** "Google doesn't use your prompts … or responses to improve our products". Data is logged for a limited period for abuse detection only. The pricing page repeats this for every model ("Used to improve our products: Free = Yes, Paid = No").
- **What counts as paid:** "Your access to Gemini API is a 'Paid Service' **only when accessing the API through a Cloud Project associated with an active billing account**." The AI Studio *UI* is treated as paid if the account has *any* billed project, but that rule does **not** extend to the API.
  - → A **separate no-billing project gives real, free programmatic access** (subject to the unpublished free quotas), **but under Unpaid terms**: training use plus human review.
- **Region rule:** EEA, Switzerland and UK: "You may use only Paid Services when making API Clients available to users" in those regions.
- **Implication for us:** the mock data is synthetic, but the challenge text and policy docs are confidential ("please don't post the challenge…").
  - Sending them to a human-reviewed, trainable endpoint isn't "posting publicly", but it is avoidable disclosure.
  - Use a **billed (Tier 1) key** for real runs. Allow the free key only by explicit opt-in, and never as silent failover.

## 5. Provider abstraction and failover

```
LLM_PROVIDER=gemini            # gemini | anthropic | openai
GEMINI_PRIMARY_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-3.1-flash-lite   # different model = separate per-model quota bucket
GOOGLE_API_KEY=…               # billed project (Paid terms)
GEMINI_FREE_API_KEY=…          # optional, no-billing project (Unpaid terms)
GEMINI_ALLOW_FREE_TIER=0       # must be 1 to ever use the free key; never auto-selected on 429
LLM_TIMEOUT_S=2.5  LLM_MAX_ATTEMPTS=2
```

Keep the interface small: `complete(messages, tools, allowed_tools, response_schema) -> {tool_calls | final_json, usage, model}`. Adapters for Gemini, Anthropic and OpenAI all return the same normalized object. Log `model` and token usage on every answer line for the eval notes.

| Error (generateContent / SDK) | Retry same model? | Failover? | User-facing behaviour |
|---|---|---|---|
| 429 RESOURCE_EXHAUSTED, per-minute limit | 1× short jittered backoff | Yes, to the fallback model (separate quota) | Transparent |
| 429 RESOURCE_EXHAUSTED, daily quota | No | Yes, to the fallback model or other provider | Transparent. Alert the operator |
| 503 UNAVAILABLE / 500 INTERNAL / 502 | 1× | Yes | Transparent |
| 504 DEADLINE_EXCEEDED / client timeout | No (latency budget) | Yes | Transparent |
| 404 NOT_FOUND (model ID) | No | Yes, plus a config error at startup | Transparent. Fix the config |
| 400 INVALID_ARGUMENT (bad schema/request) | No | No, it's a bug | Safe escalation reply ("connecting you to an agent") and log it |
| 400/401 invalid API key (**U:** the classic API returns 400 `API_KEY_INVALID`; the new errors page lists 401) | No | Other *provider* only | Escalation reply. Fail fast at startup |
| 403 PERMISSION_DENIED / 400 FAILED_PRECONDITION (billing, region) / 402 prepay depleted | No | Other provider (**not** the free key unless opted in) | Escalation reply |
| `finish_reason` SAFETY / RECITATION / PROHIBITED_CONTENT | No | No | Route `escalate` with a neutral message |
| MALFORMED_FUNCTION_CALL / `too_many_tool_calls` | 1× with the repair hint | Fallback model | Otherwise escalate |
| `missing_thought_signature` | No | No, it's a bug | Escalate and log |

**Rule:** the pipeline never answers deterministically *instead of* the LLM. If every LLM path fails, the only deterministic output is a safe `escalate` route. That meets the brief's intent and is honest.

## 6. Cost math: 100k questions/day at $50/day → **$0.0005 per question**

**Assumptions (U):**
- About 600 tokens of system rules, 2,200 of policy corpus, about 400 of tool schemas and about 50 for the question, for a prefix of about 3.3k tokens.
- Tool round trip adds about 600 tokens.
- Output of about 150–250 tokens with `minimal` thinking.

**Design A** is a two-call tool loop (call 1 → function call, call 2 → answer). It averages about 1.6 calls per question: about 5.6k input and 250 output tokens.

**Design B** is a single call. The user's account/order data is prefetched deterministically (it's tiny) and injected, and the model returns `{route, answer}`. Tools stay for policy lookup or escalation. It uses about 3.5k input and 150 output tokens.

| Model | A, no cache | A, cached prefix | B, no cache | B, cached prefix |
|---|---|---|---|---|
| gemini-3.1-flash-lite | $0.0018 | ~$0.0006 | $0.0011 | **~$0.00036 ✓** |
| gemini-3.5-flash-lite | $0.0023 | ~$0.0009 (if caching applies, **U**) | $0.0014 | ~$0.0005 (if caching applies) |
| gemini-3.8-flash (promo; ×2 from 2027) | ~$0.006 | ~$0.002 (below the 4,096-token implicit minimum) | ~$0.0033 | ~$0.0012 ✗ |
| Claude Haiku 4.5 ($1/$5, cache read $0.10) | ~$0.0073 | ~$0.0027 | ~$0.0043 | ~$0.0012 ✗ |
| OpenAI gpt-5-nano ($0.05/$0.40) / gpt-5-mini ($0.25/$2) | $0.0004 / $0.0019 | lower | $0.0002 / $0.0012 | ✓ / ~✗ |

Haiku prices are from the [Claude pricing page](https://platform.claude.com/docs/en/about-claude/pricing) and include about 500 tool-system tokens. OpenAI prices are from its [pricing page](https://developers.openai.com/api/docs/pricing).

**Takeaways:**
- Output tokens dominate once the prefix is cached, so keep answers short and thinking minimal.
- Retrieving the top 2 docs instead of the full corpus cuts the prefix to about 1.5k tokens and removes the need for caching.
- Cache hits are also a latency win.

**p95 latency (U: no official numbers; measure it in the eval runs).**
- A Flash-Lite call with `minimal` thinking, about 3.5k input and 150 output tokens is typically sub-second to about 1.5s.
- Design A's two sequential calls risk more than 3s at p95, especially with retries.
- Design B plus a 2.5s timeout plus one failover fits p95 ≤ 3s more comfortably.
- 3.8 Flash at `medium` thinking likely breaks it.

## Recommendation

1. **Provider:** Gemini on a **billed Tier-1 project** (Paid terms: no training, no human review). Primary `gemini-3.5-flash-lite` with `thinking_level=minimal`, fallback `gemini-3.1-flash-lite`, explicit model IDs, SDK `google-genai==2.25.0`, calling `generate_content`.
2. **Loop:** manual tool loop (auto function calling off). Session-scoped tools with `allowed_function_names` and `VALIDATED` mode. Final answer as structured JSON. Retry once, then fail over, then a safe `escalate`.
3. **ADR cost story:** Design B (prefetch the user's data and make one call) on 3.1 Flash-Lite with a cached or retrieved prefix gives about $0.00036/question, about $36/day. State that the 2-call loop and 3.8 Flash are 2–10× over budget. Gemini 3.8 Flash doubles in price on 2027-01-01.
4. **Free key:** a no-billing project gives genuine free API access, but only use it for smoke tests with opt-in, given human review and the confidentiality of the challenge.

## Open questions

- Is the environment's `GEMINI_API_KEY` from a billed project? `models.list` can't tell. Check AI Studio → Billing / Rate limits.
- What are the actual free and Tier-1 RPM/RPD for 3.5 and 3.1 Flash-Lite? They're only visible in AI Studio.
- Does 3.5 Flash-Lite have caching or not (pricing page vs model page)? What are the implicit and explicit minimums for Flash-Lite?
- Does `gemini-3.1-flash-lite` accept `thinking_level=minimal`? What is its default?
- Real p95 latency: log per-call latency in the first eval run.
