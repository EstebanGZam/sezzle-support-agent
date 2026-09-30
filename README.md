# Sezzle Support Agent (take-home)

An LLM shopper-support assistant. It answers from the 12 policies, looks up the caller's own orders through one read-only, user-scoped tool, and escalates human-only matters. Code enforces authorization, output validation and safe failure; the LLM interprets and writes every answer (`DECISIONS.md` ADR-1).

## Run
```bash
uv sync --locked                                   # or: pip install -r requirements.txt (Python 3.12)
cp .env.example .env                               # set ONE provider key (see below)
LLM_PROVIDER=fake python3 run_cases.py cases/golden_visible.jsonl out.jsonl        # offline smoke
uv run --env-file .env python run_cases.py cases/golden_visible.jsonl out.jsonl    # real LLM
uv run python evals/score.py cases/golden_visible.jsonl out.jsonl --trace out.trace.jsonl
uv run pytest -q                                   # 724 offline tests (fake LLM, no network)
```
- **Output:** `{id, route, answer}` per line, plus `<answers>.trace.jsonl` and `<answers>.config.json` (models, `PROMPT_VERSION`, credential fingerprint — never the key).
- **Providers:** `LLM_PROVIDER=gemini` reads only `GOOGLE_API_KEY`; `LLM_PROVIDER=groq` reads only `GROQ_API_KEY`. For Groq free-plan runs, keep pacing on and `CASE_DEADLINE_S=180`.

## Where to look
- `DECISIONS.md`: the 3 ADRs.
- `ITERATION.md`: runs, failure taxonomy, deltas.
- `evals/runs/`: unedited run artifacts.
- `PROMPTS.md`: build prompts, agent prompts, system prompts.
- `specs/`: requirements (SEZ/OWN/SEC), assumptions, architecture, security, evaluation.
- `docs/decision-log.md`: owner decisions.

## Honestly unfinished
- **The first run is not representative of LLM behaviour.** Runs 001–003 on Gemini hit a provider-wide 503/504 incident (21–30 of 35 cases ended in safe failure). The owner then moved to Groq's free plan (OD-26).
- **Iteration 2 (prompt v2) on the dev set is confounded.** Groq's free daily quota ran out, so dev ran mostly on gpt-oss-20b instead of 120b (`ITERATION.md` §3). A clean 120b rerun and the final holdout run need quota.
- **Remaining behaviour failures:**
  - GROUNDING_MISS: policy consequences omitted, e.g. how a refund applies to unpaid installments.
  - ROUTE_MISS: the shopper's own order is not looked up when the message also carries injected text.
  - Some over-refusal.
- **No explicit prompt caching.** Measured cost is ≈3× the $0.0005/question budget at Gemini Flash-Lite list prices (ADR-3). Caching and retrieval are the next trades.
- **Not built:** CI workflow; concurrency (sequential by design, with a clean path); zip automation (use `git archive`).
- **Key assumptions** (`specs/assumptions.md`):
  - A-04: reviewers need a Gemini or Groq key.
  - A-08: foreign/nonexistent order IDs → route `tool`.
  - A-09: out-of-scope → `policy`.
  - A-15: an explicit request for a human → `escalate`.
