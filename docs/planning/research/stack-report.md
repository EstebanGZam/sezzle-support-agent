# Stack research — Python-first, Gemini primary (checked 2026-09-27)

Legend: **V** = verified on an official page (URL given) · **U** = unverified, assumption, or community source only.
The "Updated" dates are the pages' own "last updated" stamps.

## 1. Spring Boot option

| Claim | V/U | Source |
|---|---|---|
| Spring AI 2.0.1 (stable) ships `spring-ai-starter-model-google-genai`. It supports the Gemini Developer API (API key) and Vertex. | V | https://docs.spring.io/spring-ai/reference/api/chat/google-genai-chat.html |
| `GoogleGenAiChatModel` supports tool calling (tool choice AUTO/ANY/VALIDATED/NONE) and structured output (native schema plus output converters). | V | same |
| It is built on the official `com.google.genai.Client` Java SDK. | V | same |
| Java SDK `com.google.genai:google-genai` 1.73.0 is GA. It needs Java 11+ today; the upcoming 2.0.0 needs Java 17+. It has function calling (AFC), `responseSchema`, and an async namespace. | V | https://github.com/googleapis/java-genai |
| Spring AI handles Gemini 3 thought signatures correctly across tool turns. | U | not found in the docs |
| Setup effort: roughly 30–45 min more than Python (Maven/Gradle, bean config, record DTOs, JSONL CLI runner). The required contract is also `python3 run_cases.py`, so you'd need a Python shim or subprocess anyway. | U (judgment) | — |

**Verdict:** it's viable, but it costs time in a 2-hour budget and gives no grading benefit ("provider choice / scaffolding not graded").

## 2. Python LLM abstraction options

| | Raw `google-genai` | Pydantic AI (`pydantic-ai-slim[google]`) | LiteLLM |
|---|---|---|---|
| Version / maturity | 2.25.0, 2026-09-22 (V, https://pypi.org/project/google-genai/) | 2.51.0, 2026-09-25, "5 - Production/Stable", MIT (V, https://pypi.org/project/pydantic-ai-slim/) | Mature, widely used (U: I didn't check the release page) |
| Gemini / OpenAI / Anthropic / Ollama | Gemini only | All four, plus "OpenAI-compatible" through `OpenAIChatModel`. `FallbackModel` chains providers (V, https://pydantic.dev/docs/ai/models/overview/) | All of them through an OpenAI-shaped `completion()` |
| Tool calling | Yes | Yes (typed tools, deps injection) | Yes. Gemini `response_schema` works, `reasoning_effort` maps to `thinking_level` on Gemini 3+, and thought signatures are kept in `provider_specific_fields` (V, https://docs.litellm.ai/docs/providers/gemini) |
| Structured output | Pydantic schema (V, §7) | `output_type=PydanticModel` | `response_format` |
| Offline tests | Hand-rolled fakes | `TestModel`, `FunctionModel`, `Agent.override`, and `models.ALLOW_MODEL_REQUESTS=False` (V, https://pydantic.dev/docs/ai/guides/testing/) | Mock responses (U) |
| Dependency weight | Small (httpx, pydantic) | Slim core plus one extra (V: slim with per-provider extras) | Heavier: many transitive deps (U) |
| Lock-in risk | Gemini-only API shape | Low: the provider is swappable, but the framework concepts (Agent, RunContext) spread through your code | Low for the provider. Adds a translation layer that can lag new Gemini features (U) |

## 3. Gemini OpenAI-compatible endpoint
Source: https://ai.google.dev/gemini-api/docs/openai (Updated 2026-09-02)

| Question | Answer | V/U |
|---|---|---|
| Base URL | `https://generativelanguage.googleapis.com/v1beta/openai/` | V |
| Function calling | Supported | V |
| Structured output (`response_format` JSON schema, Pydantic/Zod parse helpers) | Supported | V |
| Gemini 3 thought signatures | "Gemini 3 supports OpenAI compatibility for thought signatures in chat completion APIs" | V |
| `reasoning_effort` | Mapped to `thinking_level` / `thinking_budget`. Reasoning can't be turned off on 2.5 Pro or Gemini 3 | V |
| Gemini-specific features | Passed through `extra_body`: `cached_content`, `thinking_config`, safety settings, grounding | V |
| Maturity | "still in beta"; some parameters are "silently ignored" | V |
| One openai-SDK code path for Gemini + OpenAI + Ollama | Works for the basics: chat, tools, JSON output. Ollama exposes an OpenAI-compatible `/v1` (U: I didn't check Ollama's docs). Differences show up in strict-schema support, thought signatures, and `extra_body` extensions | Partly V |

**Limitations:** it's beta, parameters can be dropped without an error, and caching and thinking control need `extra_body`, which is Gemini-specific. So the code path isn't truly portable.

## 4. Context caching (the cost-critical item)

| Claim | V/U | Source |
|---|---|---|
| Implicit caching is on by default for Gemini 2.5 and newer. Put the shared content first in the prompt. | V | https://ai.google.dev/gemini-api/docs/caching (Updated 2026-09-02) |
| Implicit minimums: 3.5 / 3.6 / 3.7 / 3.8 Flash and 3.1 Pro Preview = **4,096**; 2.5 Flash and 2.5 Pro = 2,048. **Flash-Lite isn't listed at all.** | V (the gap is V) | same, plus https://ai.google.dev/gemini-api/docs/generate-content/caching (Updated 2026-09-11) |
| Explicit caching (`caches.create`) default TTL is **1 hour**. You can change it with `ttl='3600s'` or with `caches.update`. It "can be manually enabled on most models." | V | https://ai.google.dev/gemini-api/docs/generate-content/caching ; https://googleapis.github.io/python-genai/ |
| The Interactions API supports implicit caching only | V | https://ai.google.dev/gemini-api/docs/caching |
| Explicit-cache minimum for 3.1 or 3.5 Flash-Lite | **U: not documented.** A community forum report (2026-08-19) says the API enforces 2,048 on 2.5 Flash-Lite, and the docs omit it: https://discuss.ai.google.dev/t/context-caching-docs-list-wrong-minimum-token-count-for-gemini-2-5-flash-flash-lite-missing-entirely/178942 | U |
| 3.5 Flash-Lite model page lists "Caching: Supported", 1,048,576 input tokens, and function calling, structured outputs and thinking | V | https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite |

**Pricing** (https://ai.google.dev/gemini-api/docs/pricing, Updated 2026-09-24; standard tier, per 1M tokens):

| Model | Input | Output | Cached input | Storage |
|---|---|---|---|---|
| `gemini-3.1-flash-lite` (Stable) | $0.25 | $1.50 | $0.025 | $1.00 per hour |
| `gemini-3.5-flash-lite` (Stable) | $0.30 | $2.50 | $0.03* | $1.00 per hour |
| `gemini-2.5-flash-lite` (Limited Access for new projects) | $0.10 | $0.40 | $0.01 | $1.00 per hour |

\*My extraction of the pricing page also returned "Not available" for standard-tier caching on 3.5 Flash-Lite. That conflicts with the model page, so treat it as **U** and re-check it by eye.

**Is a ~3.3k-token policy prefix cacheable?** Probably **not reliably**:
- It's below the 4,096 minimum that is documented for every 3.x Flash model.
- The Flash-Lite minimum is undocumented. It *might* be 2,048 if 3.x Flash-Lite behaves like 2.5 (U).
- To be safe, pad the prefix above 4,096 (for example, add few-shot examples), or confirm with `usage_metadata.cached_content_token_count` on a real call.

**Why it matters for the ADR** (derived arithmetic, not a quote): 100k requests/day × ~3.3k prefix tokens ≈ 330M input tokens/day.
- On 3.1 Flash-Lite: ≈ **$82/day uncached** versus ≈ **$8/day cached**, before output tokens.
- Explicit-cache storage for 3.3k tokens × 24 h ≈ $0.08/day, which is negligible.
- **Conclusion:** the $50/day budget is only reachable with caching, retrieval that shrinks the prefix, or both.

## 5. google-genai async client in FastAPI

| Claim | V/U | Source |
|---|---|---|
| `client.aio` "exposes all the analogous async methods". Supports `async with Client().aio` and `await aclient.aclose()`. | V | https://googleapis.github.io/python-genai/ |
| Uses httpx by default. `google-genai[aiohttp]` is an option for faster async, configured with `HttpOptions(async_client_args=...)`. | V | same ; PyPI |
| The docs recommend explicitly closing clients to release HTTP connections | V | PyPI |
| The client is thread-safe and safe to share as a singleton with a pooled connection | **U**: not stated. It's standard practice with an httpx-backed client. Create one in the FastAPI `lifespan` and `aclose()` it on shutdown. | U |
| Automatic function calling (AFC) behaviour changes in 3.0.0. Pin `google-genai>=2.25,<3`. | V | PyPI |

## 6. FastAPI concurrency and rate limiting

| Claim | V/U | Source |
|---|---|---|
| `def` endpoints run in a threadpool; `async def` endpoints run on the event loop. Never call blocking code inside `async def`. With `client.aio`, use `async def`. | V | https://fastapi.tiangolo.com/async/ |
| slowapi 0.1.10 (2026-06-13) is a community project (maintainers Laurent Savaete and twcurrie), ported from flask-limiter. It is **not** an official FastAPI project and is still pre-1.0. | V | https://pypi.org/project/slowapi/ |
| Simpler alternative: an in-process `asyncio.Semaphore` to cap concurrent LLM calls, plus a per-user token bucket in a dict | U (design) | — |

FastAPI itself is optional. The graded interface is the `run_cases.py` CLI, and deployment isn't required.

## 7. Pydantic v2

| Claim | V/U | Source |
|---|---|---|
| `Model.model_validate_json()` and `TypeAdapter(list[Order]).validate_json()` parse with jiter. JSON mode accepts ISO date strings. `from_json(allow_partial=True)` is available from 2.7. | V | https://pydantic.dev/docs/validation/latest/concepts/json/ |
| The Gemini SDKs accept Pydantic-defined schemas for structured output | V | https://ai.google.dev/gemini-api/docs/structured-output (Updated 2026-09-23) |
| Gemini 3 can combine structured output with function calling in one call | V | same |

**Pattern:** validate the orders JSON once at load time with strict models (`Literal` statuses, `date`, `Decimal`). Constrain the LLM output to a model like `{route: Literal[...], answer: str, cited_docs: list[str]}` and re-validate it.

## 8. Python version

| Claim | V/U | Source |
|---|---|---|
| google-genai needs Python ≥ 3.10, with classifiers for 3.10–3.14 | V | https://pypi.org/project/google-genai/ |
| pydantic-ai-slim needs Python ≥ 3.10 | V | https://pypi.org/project/pydantic-ai-slim/ |
| **Recommend 3.12.** It has the broadest wheel coverage and is the least likely to break on a reviewer's machine. 3.13 also works. | U (judgment) | — |

## Recommendation
- **Python 3.12 + raw `google-genai>=2.25,<3` (`client.aio` singleton) + Pydantic v2.**
  - Use native Gemini tool calling and structured output (`route` enum).
  - Deterministic authorization and escalation go around the model.
  - Keep a thin `LLMClient` protocol of your own for swappability, with a fake for tests.
- **Pydantic AI** is the best alternative if you want `TestModel`/`FunctionModel` offline tests and cheap provider fallback. It's production-stable. Its cost is 20–30 minutes of learning the framework's idioms.
- **Skip** Spring Boot, LiteLLM, and the OpenAI-compatible endpoint as primary paths. The endpoint is beta and Gemini-specific features need `extra_body` anyway.
- **Model:** `gemini-3.1-flash-lite` (Stable, cheapest 3.x).
- **Cost ADR:** caching is decisive for the $50/day budget. Measure `cached_content_token_count`, and shrink the prefix with retrieval or pad it above 4,096 tokens.
- **Rate limiting:** a semaphore is enough. Mention slowapi as the production option.

## Open questions
1. What is the actual explicit/implicit cache minimum for 3.1 and 3.5 Flash-Lite? It's undocumented; test with one real call and read `usage_metadata`.
2. Is standard-tier caching on 3.5 Flash-Lite "Not available" on the pricing page, or was that an extraction error? Check the page by eye.
3. Is the Client thread-safe? Not documented; the singleton plus `lifespan` approach is an assumption.
4. Does Spring AI handle Gemini 3 thought signatures across tool turns? Only relevant if Java is reconsidered.
