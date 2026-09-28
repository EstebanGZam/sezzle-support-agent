Verify, from OFFICIAL docs only (cite URL + mark V/U), the external facts needed for a tech-stack decision matrix for the take-home assistant (Python-first, Gemini primary). Answer each briefly: (1) Spring Boot option: does Spring AI currently support Gemini (Google GenAI / Vertex) with tool calling + structured output? Is there an official Google GenAI Java SDK (com.google.genai) and its maturity? Rough setup effort vs Python for a 2h build. (2) Python LLM abstraction options besides raw google-genai: Pydantic AI (ai.pydantic.dev) — Gemini/OpenAI/Anthropic support, tool calling, structured output, testing with TestModel/FunctionModel, dependency weight; LiteLLM — provider portability and Gemini tool calling. Note maturity and lock-in risk. (3) Gemini OpenAI-compatible endpoint (ai.google.dev/gemini-api/docs/openai): does it support function calling, structured output (response_format json_schema), Gemini 3 thought signatures, and can one openai-SDK code path serve Gemini + OpenAI + Ollama? Limitations. (4) Gemini explicit context caching (client.caches.create): minimum token count for gemini-3.1-flash-lite / 3.5-flash-lite, TTL, storage price; implicit caching minimums for Flash-Lite. Is ~3.3k tokens of shared policy prefix cacheable? (5) google-genai async client (client.aio) suitability for concurrent requests inside FastAPI; is the Client thread-safe / reusable as a singleton; connection pooling. (6) FastAPI concurrency basics relevant here: async endpoints vs sync, and lightweight in-process rate limiting options (e.g. slowapi) — provenance/maintenance. (7) Pydantic v2 for validating the orders JSON and structured LLM output. (8) Python version: which versions google-genai 2.x supports; recommend 3.12 vs 3.13. Keep it to ~1000-1400 words, table-heavy. Do NOT install anything or call paid APIs. Write to /tmp/claude-1000/-home-esteban-Documents-Sezzle-sezzleaiengineertakehomechallenge/ccff6d6a-aaa3-400c-9a8e-77971ff64c4f/scratchpad/research/stack/report.md.

--- context ---
# Shared research brief (lead → teammates)

Today: 2026-09-27. You are a read-only RESEARCH teammate in an advisory phase.

## Context
The user is preparing a Sezzle "Applied AI Engineer" take-home: build an LLM-powered
shopper-support assistant over 12 short markdown policy docs + a JSON file of mock
accounts/orders (installment schedules, frozen `today` = 2026-07-01). The assistant
must answer policy questions, look up order data, and escalate what it shouldn't touch.
Key facts from the official brief (PROMPT.md / SUBMISSION.md):
- ~2 hour time budget; honest "unfinished" notes graded positively.
- AI coding tools expected; prompts must be logged in PROMPTS.md.
- "A solution with no working LLM in the pipeline does not meet the brief."
  Deterministic logic AROUND the model is welcome; deterministic answering INSTEAD of it is not.
- Any LLM provider allowed. Data is synthetic.
- Contract: `python3 run_cases.py <cases.jsonl> <answers.jsonl>`; input `{id, question, user_id}`,
  output `{id, route, answer}`, route in policy|tool|both|escalate. Hidden test set graded by regex
  must_include / must_not_include.
- Deliverables: code, DECISIONS.md (exactly 3 ADRs, ≤~10 lines each), first+final eval runs with
  iteration note, PROMPTS.md, half-page README.
- Design constraint for an ADR: 100k questions/day, ~$50/day inference budget, p95 ≤ 3 s.
- Grading order: design decisions > iteration loop > LLM engineering (grounding, what the model is
  STRUCTURALLY prevented from doing) > escalation/authorization judgment > how AI tools were directed.
  Scaffolding quality, provider choice, LOC are NOT graded.
- Submission: zip OR private GitHub/GitLab repo shared with reviewer. "Please don't post the
  challenge or your solution publicly." Public deployment is NOT required by the brief.

## Hard rules for you
- Do NOT install anything, create repos, deploy, launch cloud sessions, or spend credits.
- Do NOT modify files outside your own output directory. Never print or write API keys/tokens.
- Do NOT upload or paste the assessment materials to any external service.
- Prefer OFFICIAL sources; cite URLs inline. Mark each claim VERIFIED (with source) or UNVERIFIED/ASSUMPTION.
  If something changed recently or you can't confirm it, say so. Pricing/limits: quote the page and date.
- Be concise and decision-oriented: the lead needs a recommendation, not an encyclopedia.
  Target 600–1500 words unless told otherwise. End with "Recommendation" and "Open questions".
- Write your final report to the report.md path given in your task, then reply with a 5-line summary.
