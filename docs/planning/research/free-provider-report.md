# Free inference provider for the support-assistant CLI — research report

Date: 2026-09-28. Researcher: read-only research teammate. Nothing was installed, no LLM API was called, and no credentials or assessment content were sent anywhere. Official docs were fetched with anonymous GETs (the `.md` variants of the doc pages).

Legend: **V** = checked today against the cited official page. **U** = not verified (inferred, taken from a secondary source, or depends on account-specific settings).

---

## 1. GroqCloud

### 1.1 Models available today (https://console.groq.com/docs/models)
| Model ID | Status | Context | Max completion | Speed claim | Notes |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | Production | 131,072 | 65,536 | ~500 tok/s | **V** |
| `openai/gpt-oss-20b` | Production | 131,072 | 65,536 | ~1000 tok/s | **V** |
| `qwen/qwen3.8-27b` | **Preview** ("evaluation purposes only… may be discontinued at short notice") | 131,072 | 16,384 | ~450 tok/s | **V** |
| `openai/gpt-oss-safeguard-20b` | Preview (safety classifier) | 131,072 | 65,536 | 1000 | not a general assistant model **V** |
| `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `minimaxai/minimax-m2.7` | Marked "Enterprise / Contact Sales" | — | — | — | **Not in the Free-plan rate-limit table**, so they are probably not usable on the free plan **V** (table) / **U** (actual availability) |

### 1.2 Free-plan rate limits (https://console.groq.com/docs/rate-limits) — V
| Model | RPM | RPD | TPM | TPD |
|---|---|---|---|---|
| openai/gpt-oss-120b | 30 | 1K | **8K** | **200K** |
| openai/gpt-oss-20b | 30 | 1K | 8K | 200K |
| openai/gpt-oss-safeguard-20b | 30 | 1K | 8K | 200K |
| qwen/qwen3.8-27b | 30 | 1K | 8K | 200K |

- Limits apply per organisation and per model. The first limit you reach triggers throttling. Some organisations also get separate ITPM/OTPM caps, visible on https://console.groq.com/settings/limits. **V**
- "Cached tokens do not count towards your rate limits." The prompt-caching page adds: "cached tokens are subtracted from your limits after processing, so it's still possible to hit your limits if you are sending a large number of input tokens in parallel requests." **V** (https://console.groq.com/docs/prompt-caching)
- Response headers: `x-ratelimit-limit-requests` / `remaining-requests` / `reset-requests` all refer to **RPD**. `x-ratelimit-*-tokens` refers to **TPM**. `retry-after` (seconds) is sent only with a 429. **V**
- The page calls this "a high level summary and there may be exceptions". The real numbers are on your account's Limits page. **V**
- Developer (paid) base limits for gpt-oss-120b/20b are 250K TPM and 1K RPM. **V** (models page)

### 1.3 Tool calling (https://console.groq.com/docs/tool-use, API ref https://console.groq.com/docs/api-reference) — V
- "All models hosted on Groq support tool use." gpt-oss-120b/20b support local and remote tools and JSON mode, but **not parallel tool calls**. That is fine for our single tool. Qwen 3.8 27B supports parallel calls.
- `tool_choice` accepts `none` | `auto` | `required` | `{"type":"function","function":{"name":…}}`. The default is `auto` when tools are present. `parallel_tool_calls` defaults to true. Max 128 functions.
- `disable_tool_validation` exists. If true, Groq returns tool calls without checking them against `tools`.
- Unsupported OpenAI fields that cause a **400**: `logprobs`, `top_logprobs`, `messages[].name`. `temperature=0` is converted to 1e-8. `n` must be 1. (https://console.groq.com/docs/openai) **V**
- Cerebras' gpt-oss-120b page warns that the model "may call tools that aren't directly specified". This is a model trait, so it probably applies on Groq too **U**. Keep validating the tool name.

### 1.4 Structured outputs (https://console.groq.com/docs/structured-outputs) — V
- `response_format: {"type":"json_schema","json_schema":{…,"strict":true}}` uses constrained decoding and is supported on **gpt-oss-20b, gpt-oss-120b and qwen3.8-27b**. Best-effort mode (`strict:false`) adds gpt-oss-safeguard-20b. Other models only have `json_object` mode.
- Strict-mode rules: every property must be listed in `required`, and every object needs `additionalProperties:false`. Our schema {answer, escalation_reason enum, policy_applied bool, cited_policies string[]} fits as long as all four fields are required.
- **"Streaming and tool use are not currently supported with Structured Outputs."** You cannot send `response_format=json_schema` together with `tools` in the same request.
- **Standard workaround for call 1:** do not send `response_format`. Send two function tools instead: `get_my_orders` and `submit_answer`, where `submit_answer`'s parameters are the answer schema. Use `tool_choice="required"` so the model must either look up orders or submit an answer. Parse `submit_answer` arguments as the final answer. For **call 2** (tools disabled) use `response_format` json_schema with `strict:true` and no `tools`. This matches the design we already have. Alternatively, call 2 can keep only `submit_answer` with `tool_choice={"type":"function","function":{"name":"submit_answer"}}`. **V** (the parameters exist); workaround pattern **U** (design advice, not a Groq doc statement). Groq documents no `strict` flag for tool parameters, so tool-argument JSON is best-effort; validate it and use the repair call **U**.
- `reasoning_format` must be `parsed` or `hidden` when using tool calling or JSON mode. `raw` returns a 400. **V** (https://console.groq.com/docs/reasoning)

### 1.5 Reasoning (gpt-oss) — V
- `reasoning_effort`: gpt-oss supports `low` | `medium` | `high`, with **default `medium`**. Qwen 3.8 27B supports `none` | `default` | `low` | `medium` | `high` and defaults to `none`. Unsupported values return a 400.
- `include_reasoning` (bool) and `reasoning_format` cannot be used together. With `parsed`, reasoning comes back in `message.reasoning`.
- Reasoning tokens are generated output. They count toward completion tokens and therefore toward TPM and TPD **U** (standard behaviour, not stated explicitly). Use `reasoning_effort="low"` and set `max_completion_tokens` explicitly, e.g. 1024–1500. The docs' default of 1024 "may be too low" for heavy reasoning.
- Groq advises reasoning models to "avoid system prompts" and put instructions in the user message. This is a quality tip, not a requirement **V**.

### 1.6 Endpoint and SDK — V
- OpenAI-compatible base URL `https://api.groq.com/openai/v1`, route `/chat/completions`. The Responses API is also available.
- The official `groq` Python SDK (`pip install groq`) has sync and async clients and typed params (https://console.groq.com/docs/libraries). The `openai` SDK also works with `base_url` set. Plain `httpx` works too because it is a plain REST/JSON API. For a small CLI with retry control, httpx or the `openai` SDK avoids a vendor dependency. The `groq` SDK adds typed Groq-only params (`reasoning_format`, `service_tier`) **U** (judgement).
- `seed` gives best-effort determinism. Check `system_fingerprint` for backend changes.

### 1.7 Error codes (https://console.groq.com/docs/errors) — V
- **429** Too Many Requests. Honour `retry-after`.
- **413** Request Entity Too Large. The docs only say "request body is too large". In practice Groq also returns 413 when a single request's tokens exceed your TPM, e.g. a >8K request on the free plan **U**.
- **498** "Flex Tier Capacity Exceeded". This only applies to `service_tier=flex`, which is **paid only** (https://console.groq.com/docs/flex-processing), so we should not see it.
- **500/502/503** are server errors. "You will not be charged for requests that return server error codes." 503 means maintenance or overload, so retry with backoff.
- Also 400 (schema or param errors, including best-effort JSON failures), 422 (semantic/hallucination), 401, 403, 404.
- The error body is `{"error":{"message","type"}}`.

### 1.8 Prompt caching (https://console.groq.com/docs/prompt-caching) — V
- Automatic, free, with a 50% discount on cached input. **Only on gpt-oss-20b, gpt-oss-120b and gpt-oss-safeguard-20b.** It matches exact prefixes and expires after 2 h without use. Hits are "not guaranteed". The cache is held in volatile memory only.
- Put the static prefix first (system prompt + tool defs + ~2.2k policy text) and variable content last.

### 1.9 Latency claims — V (marketing numbers from the models page)
gpt-oss-120b ~500 tok/s and gpt-oss-20b ~1000 tok/s. At ≤600 output tokens that is about 1–2 s of generation plus queueing. Groq publishes no end-to-end latency SLA **U**.

---

## 2. Groq data handling — V unless noted
Sources: https://console.groq.com/docs/your-data and the Services Agreement https://console.groq.com/docs/legal/services-agreement
- "**By default, Groq does not retain customer data for inference requests.**" Inputs and outputs may be logged temporarily **only** to troubleshoot reliability problems or investigate abuse. Those logs are kept "up to **30 days**" unless the law requires longer. Data is stored in US GCP.
- **Zero Data Retention (ZDR):** "All customers may enable Zero Data Retention (ZDR) in Data Controls settings" (https://console.groq.com/settings/data-controls). With ZDR on, reliability/abuse logging is off. Chat Completions is listed as ZDR-eligible. The Services Agreement §4.2 says "Eligible Customers", so check that the toggle is available on a free org **U**.
- **Training:** Services Agreement §4.2 says "Groq is not permitted to use Inputs or Outputs for training or fine-tuning any AI Model Services or other models, unless explicitly granted permission or instructed by Customer." Inputs and Outputs are defined as Customer Data, and the customer keeps the IP.
- **Free vs paid:** the agreement does not describe a separate free-tier data regime. §5.1 simply notes that some services may be "fee-free". Liability for free services is capped at $5,000 (§14.2). **V** that no carve-out exists in the text we read. **U** that nothing else applies.
- **Preview models count as "Beta Services"** (§3.6): "Beta Services are not Cloud Services under this Agreement… Groq's DPA and BAA do not apply to Beta Services." This means **qwen/qwen3.8-27b (Preview) carries weaker contractual terms than the production gpt-oss models.** This is a reason to pick gpt-oss-20b rather than Qwen as the fallback.
- Privacy policy (https://groq.com/privacy-policy) covers website and account data. The services agreement is what governs API content.

---

## 3. Alternatives (free tier only)

### 3.1 Cerebras Inference
Sources: https://inference-docs.cerebras.ai/support/rate-limits, https://inference-docs.cerebras.ai/models/overview
- **There is no permanently free tier.** "The Free Trial is time- and credit-bounded: $5 in credits that expire 30 days after they're granted." You must add a verified payment method before the API works. **V**
- Models: `gpt-oss-120b` (65k context on the free trial) and `qwen-3.8-27b`. Speed claims ~3000 and ~1850 tok/s. **V**
- Free Trial limits (rate-limits page): **5 RPM**, 30K uncached TPM, 90K total TPM, 1M TPH, **1M TPD**. **V** The gpt-oss model page contradicts this: "30 requests/min, 60k input tokens/min, 1M tokens/day". **V** that the two pages disagree. Plan for 5 RPM.
- Pricing: gpt-oss-120b costs $0.35 per 1M input tokens and $0.75 per 1M output tokens. One run is roughly 0.5M tokens, about $0.2, so $5 covers many runs. **V** for prices; cost estimate **U**.
- Tool calling supports `none`/`auto`/`required`/named function, **strict tool schemas (`tools[].function.strict`)**, parallel calls and multi-turn. Structured outputs support json_schema with `strict:true` on both models. **"Do not combine `tools` and `response_format`… call tools first and format the result in a separate structured-output request"**. This is the same pattern as Groq. **V** (https://inference-docs.cerebras.ai/capabilities/tool-use, …/structured-outputs)
- Rate-limit estimation includes `max_completion_tokens`, so set it low. **V**
- Data: "We do not retain inputs and outputs associated with our training, inference and chatbot Services." (privacy policy, effective 2024-08-27, https://www.cerebras.ai/privacy-policy) **V**. No training on inference payloads **U** (follows from no retention; not stated as a separate clause).
- Fit: technically the best (strict tools, larger quotas). Budget and timing are the problems: it needs a card, and credits expire 30 days after they are granted, which may be before the grader's hidden run.

### 3.2 OpenRouter `:free` models
Sources: https://openrouter.ai/docs/api/reference/limits, https://openrouter.ai/api/v1/models, https://openrouter.ai/docs/guides/privacy/provider-logging
- Limits: **20 RPM**. **50 requests/day** if you have bought fewer than 10 credits lifetime. **1000/day** if you have bought at least 10. **V**
- There are 16 `:free` models today. **There is no gpt-oss `:free` variant.** Models that list tools + response_format + structured_outputs include `nvidia/nemotron-3-super-120b-a12b:free` (upstream: Nvidia), `dots-studio/dots-3-note-preview:free` and `liquid/lfm-2.5-2.6b:free`. `qwen/qwen3.8-27b:free` (upstream: ModelRun, fp4) has tools and structured_outputs. **V** (models API)
- The Nemotron free endpoint's `supports_tool_choice` shows `none:false`. That breaks the "tools disabled" call pattern unless you drop `tools` entirely. **V**
- Data: OpenRouter itself does not train on prompts and does not store content unless you opt in. Free endpoints, however, are "served by providers whose data policy may allow training on your prompts". Some free models state that prompts "are logged by the model creator for feedback and training". There are separate account switches for paid and free training. If you turn training off, free routes may return 404. **V** for the provider-logging page mechanics. The per-model logging notices come from a search summary **U**.
- Fit: **poor**. 50 RPD without credits is below one 120-call run. The upstream providers vary and some log or train. Uptime for the Nemotron free endpoint was about 94–97%.

### 3.3 GitHub Models
- **Retired.** "As of July 30, 2026, GitHub Models has been fully retired. The playground, model catalog, inference API, and bring your own key (BYOK) are no longer available to any customer." (https://docs.github.com/en/github-models) **V** Not an option.

### 3.4 Mistral La Plateforme / Mistral Studio (free "Experiment" mode)
- A free mode exists with the lowest limits (RPS, tokens per minute, tokens per month). The exact numbers are only shown on the console Limits page. **V** (https://docs.mistral.ai/admin/user-management-finops/tier), numbers **U**
- Free mode: "we may use your data (input and output) to train our artificial intelligence models". You can opt out. **V** (https://help.mistral.ai/en/articles/347617)
- Tool calling and json_schema structured output are generally supported on Mistral models **U** (not re-checked today).
- Fit: usable only after opting out of training. The throughput numbers are unknown.

### 3.5 Google AI Studio / Gemini API free tier (Unpaid Services)
- Unpaid Services terms: "human reviewers may read, annotate, and process your API input and output". Google uses it "to provide, improve, and develop Google products and services". "**Do not submit sensitive, confidential, or personal information to the Unpaid Services.**" **V** (https://ai.google.dev/gemini-api/terms, last modified 2026-03-23)
- Free rate limits are no longer published in the docs. They are shown only in AI Studio. **V** (https://ai.google.dev/gemini-api/docs/rate-limits)
- This is also the provider that had the 503/504 capacity incident. Fit: **worst for confidentiality**.

---

## 4. Fit for our workload

Assumptions per call: ~3.3k input tokens (call 2 is ~3.7k with the tool call and result), up to 600 visible output tokens, plus reasoning tokens (low effort, ~100–300 **U**). Budget about **4.2k tokens per call without caching**. A full run is 60–120 calls.

### Groq free, gpt-oss-120b (8K TPM, 200K TPD, 30 RPM, 1K RPD)
| Scenario | Calls/min (TPM-bound) | 120-call run, wall time | Calls/day (TPD-bound) |
|---|---|---|---|
| No cache hits (~4.2k/call) | ~1.9 | ~63 min | **~47** |
| ~2.5k-token static prefix cached (~1.7k uncached/call) | ~4.7 | ~26 min | ~117 |

- **TPD, not RPM, is the binding limit.** Without cache hits, one model gives fewer than half of one 120-call run per day. Even a 35-case run (~75–100 calls) does not fit. With good cache hits, about one full run per model per day is just possible. Cache hits are "not guaranteed" and cached tokens may still be "subtracted after processing". **U** until measured.
- Limits are listed per model ID. Using **gpt-oss-120b and gpt-oss-20b gives two separate 200K TPD buckets** (~400K per day). **V** (the table is per model). **U** whether the org has any cross-model cap.
- 5–8 runs in total at ~0.25–0.5M tokens each means spreading runs over several days, or trimming tokens:
  - `reasoning_effort="low"`
  - explicit `max_completion_tokens` around 800–1200
  - shorter policy excerpt, or retrieve only the relevant policies
  - only use the repair call when validation fails
  - keep the prefix byte-identical so it can be cached
- Pace calls client-side at 1 call every ~30 s. Read `x-ratelimit-remaining-tokens` (TPM) and back off on 429 using `retry-after`.
- A single request must stay under 8K TPM. 3.7k input plus `max_completion_tokens` should be ≤ ~8K, otherwise you risk a 413/429 **U**.

### Cerebras free trial (5 RPM, 30K uncached TPM, 1M TPD)
- 5 calls/min, so a 120-call run takes about 24 min. 1M TPD allows about 2 full runs per day. It meets the quota needs comfortably, but only for 30 days, needs a card, and spends $5 of credit.

### OpenRouter free
- 50 RPD is below a single run. 1000 RPD requires buying $10 of credits. Not viable at zero cost.

---

## 5. Confidentiality ("Please don't post the challenge or your solution publicly"; materials are synthetic)
| Provider (free) | Trains on prompts? | Human review / retention | Compatible? |
|---|---|---|---|
| **Groq** (production gpt-oss) | **No** (contractual, §4.2) **V** | No retention by default. Up to 30 days only for reliability/abuse. **ZDR toggle** available **V** | **Yes** (turn on ZDR) |
| Groq Preview (Qwen 3.8) | Same §4.2 wording **U**, but DPA not applicable (Beta) **V** | as above | Acceptable, but weaker |
| **Cerebras** | Not retained, so no training corpus **V/U** | "do not retain inputs and outputs" **V** | **Yes** (but needs a card and credits) |
| Mistral free | **Yes by default**, opt-out available **V** | — | Only after opting out |
| OpenRouter `:free` | Depends on upstream. Some log or train **V/U** | varies | **No / risky** unless the free-model training switch is off, and even then the upstream terms vary |
| Google AI Studio Unpaid | **Yes**, used to improve products, with human reviewers **V** | "Do not submit… confidential" **V** | **No** |
| GitHub Models | retired **V** | — | n/a |

The materials are synthetic, so the practical risk is "publication/training exposure", not personal data. Groq (production models + ZDR) and Cerebras are the ones whose terms rule out training. Google Unpaid and default Mistral free conflict with the "don't post publicly" spirit because data may be reviewed or trained on.

---

## Recommendation
- **Provider:** GroqCloud Free plan, with **Zero Data Retention enabled** in Data Controls.
- **Primary model:** `openai/gpt-oss-120b`. Settings: `reasoning_effort="low"`, `reasoning_format="hidden"` (or `parsed`), explicit `max_completion_tokens` around 1000, `temperature` about 0.2–0.6, fixed `seed`.
- **Fallback model (same provider, same production data terms, separate quota bucket):** `openai/gpt-oss-20b`. It has the same API surface: strict json_schema, tools, caching and reasoning_effort. Avoid `qwen/qwen3.8-27b` as the default fallback because it is Preview/Beta (DPA excluded, may be discontinued). Treat it as a last-resort third option.
- **Operational:** throttle to about 1 call every 30 s. Watch TPD (`x-ratelimit-*` covers only RPD/TPM, so track tokens per day yourself). Route whole runs, or alternate runs, between 120b and 20b to double the daily budget. Log `usage.prompt_tokens_details.cached_tokens` **U** (field name not re-checked) to measure cache hits.
- **If quota is still too tight:** a Cerebras free trial ($5, 30 days, card required) for gpt-oss-120b is the best terms-compatible escape hatch.

## Incompatibilities with a Gemini-shaped adapter
1. **Structured output cannot be combined with tools in one request on Groq** (and Cerebras advises against it). Gemini lets `response_schema` coexist with function declarations in some modes. Call 1 needs the `submit_answer` function tool + `tool_choice="required"` pattern. Call 2 uses `response_format` json_schema `strict:true` with no `tools`.
2. **Schema dialect:** OpenAI JSON Schema with strict rules: every field required, `additionalProperties:false` on every object, `type` as a lowercase string. Gemini's `Schema`/OpenAPI subset (uppercase `Type.STRING`, `nullable`, `propertyOrdering`) does not map directly. An optional `order_id`/`merchant` in the **tool parameters** is fine because tool params aren't strict on Groq **U**. In a strict **response** schema, optional fields must become required and nullable (`["string","null"]`).
3. **Message format:** roles are `system`/`user`/`assistant`/`tool`. Tool results need `tool_call_id`. `tool_calls[].function.arguments` is a **JSON string**, not a dict. Gemini uses `contents`, `parts`, `function_call`/`function_response`, and role `model`.
4. **Disabling tools for call 2:** in Gemini this is `tool_config` mode NONE. Here, omit `tools`, or send `tool_choice="none"`.
5. **Reasoning:** there is no Gemini `thinking_config`. Use `reasoning_effort` + `reasoning_format`/`include_reasoning` instead (the last two are mutually exclusive). `raw` together with tools or JSON returns a 400.
6. **Unsupported fields return 400:** `logprobs`, `top_logprobs`, `messages[].name`, and `n≠1`.
7. **Errors and retry:** 429 with `retry-after`, 413 (size/TPM), 503. 498 is flex-only. `x-ratelimit-*-requests` headers are **per day**. Gemini's `RESOURCE_EXHAUSTED`/503/504 handling has to be remapped.
8. **Usage accounting:** field names differ (`usage.prompt_tokens`, `completion_tokens`, `completion_tokens_details.reasoning_tokens`, cached tokens) compared with Gemini's `usage_metadata`.
9. **Caching:** implicit prefix caching only, with no explicit cache objects (Gemini has `cachedContents`). Keep the static prefix first and byte-stable.
10. **No safety-settings or `candidates` array.** A single choice comes back as `choices[0].message`, and `finish_reason` values differ (`tool_calls`, `stop`, `length`).

## Open questions
1. Who pays for or runs the **hidden grader set**: our key or theirs? If ours, Groq's TPD, or Cerebras' 30-day credit expiry, may fail at an unknown future date.
2. Do the Groq free-plan numbers on *our* org's Limits page match the doc table? Is there any cross-model TPD cap, or ITPM/OTPM split?
3. Is the ZDR toggle available on a free (unbilled) Groq org? §4.2 says "Eligible Customers".
4. Measured prompt-cache hit rate on Groq for our prefix, and whether cached tokens really stay out of TPD.
5. Does Groq's TPM pre-check count `max_completion_tokens` (as Cerebras does)? This decides the safe per-request maximum under 8K TPM.
6. Which Cerebras free-trial number is correct: 5 RPM / 30K TPM (rate-limits page) or 30 RPM / 60K (model page)?
7. How reliable is gpt-oss's tool-argument JSON without strict tool schemas on Groq? Measure how often the repair call is needed.
8. Is a two-model split (120b / 20b) acceptable for evaluation consistency, or must every run use one model?
