# Sezzle Support Agent — take-home submission

An LLM shopper-support assistant:
- It **answers** from the 12 policy docs.
- It **looks up** the caller's own orders through one read-only, user-scoped tool.
- It **escalates** human-only matters.

The LLM interprets and writes every answer. Code enforces authorization, output validation and safe failure ([ADR-1](DECISIONS.md)).

> Focused implementation and evaluation time: approximately 2h 15m (tracked independently).

## Deliverables (per `assessment/PROMPT.md`)
| Required | Where |
|---|---|
| Code + `run_cases.py` contract | [`run_cases.py`](run_cases.py), [`src/support_agent/`](src/support_agent/) |
| `DECISIONS.md` — exactly 3 ADRs | [`DECISIONS.md`](DECISIONS.md) |
| Iteration evidence — first + final run + note | [`ITERATION.md`](ITERATION.md) (the "At a glance" section first), first run [`evals/runs/001_baseline/`](evals/runs/001_baseline/), final run [`evals/runs/005_groq_prompt_v2/`](evals/runs/005_groq_prompt_v2/). All runs: [`evals/runs/`](evals/runs/), each with `answers.jsonl`, `trace.jsonl`, `score.md`, `config.json`, `NOTES.md` |
| `PROMPTS.md` — build prompts + in-system prompts | [`PROMPTS.md`](PROMPTS.md) (verbatim texts in [`docs/planning/prompts/`](docs/planning/prompts/), system prompts in [`docs/system-prompts/`](docs/system-prompts/)) |
| `README.md` — how to run + unfinished | this file |

**Supporting material:**
- Specs: [requirements](specs/requirements.md) (SEZ = Sezzle, OWN = owner, SEC = security), [assumptions](specs/assumptions.md), [architecture](specs/architecture.md), [security](specs/security.md), [evaluation](specs/evaluation.md), [tasks](specs/tasks.md).
- Decisions and reviews: [owner decision log](docs/decision-log.md) and [independent reviews](docs/reviews/).
- Inputs: [assessment inputs + provenance manifest](assessment/MANIFEST.md).
- What the submission zip contains: [`SUBMISSION_MANIFEST.md`](SUBMISSION_MANIFEST.md).

## Run it (clean machine, no development tooling needed)
Requires **Python 3.12**. No deployed service is needed; the only network calls go to the configured LLM provider.
```bash
# 1. Install (either option)
uv sync --locked                                   # uses uv.lock (includes pytest, ruff)
# or:  python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt pytest ruff

# 2. Offline smoke test — no key, fake LLM (checks the contract and pipeline, not answer quality)
LLM_PROVIDER=fake python3 run_cases.py cases/golden_visible.jsonl out/answers.jsonl

# 3. Real LLM — put ONE provider key in .env (git-ignored), never on the command line
cp .env.example .env    # then edit: LLM_PROVIDER=groq + GROQ_API_KEY=...  (or gemini + GOOGLE_API_KEY=...)
set -a; . ./.env; set +a
python3 run_cases.py cases/golden_visible.jsonl out/answers.jsonl        # the required contract
python3 run_cases.py cases/adversarial_dev.jsonl out/dev_answers.jsonl   # our adversarial set

# 4. Inspect and score
head out/answers.jsonl                              # {id, route, answer} per line
python3 evals/score.py cases/golden_visible.jsonl out/answers.jsonl --trace out/answers.trace.jsonl --out out/score.md

# 5. Tests and lint (offline, no key)
python3 -m pytest -q          # 724 tests
ruff check . && ruff format --check .
```

**Expected behaviour:**
- Each line gets `route ∈ {policy, tool, both, escalate}` and an answer.
- A trace (`out/answers.trace.jsonl`) and run config (`out/answers.config.json`) are written next to the answers. They record the model and `PROMPT_VERSION`, plus a key fingerprint, never the key.
- Provider failures produce a safe escalation line instead of crashing. An auth/billing failure writes every line and exits `3`.

**Provider caveats:**
- **`groq`** (used for the final runs): the free plan is limited to 8K tokens/min and 200K tokens/day per model. The client paces calls, so a full run takes several minutes; `CASE_DEADLINE_S=180` is the default when pacing is on.
- **`gemini`**: runs 001–003 hit a provider-wide overload incident.
- Each provider reads **only** its own key variable.

## Honestly unfinished
- **Final run caveat:** the final visible-case run (005) predates two adapter-only fixes for Groq error handling. Nothing behaviour-relevant changed afterwards ([ITERATION.md](ITERATION.md)).
- **Dev set is confounded:** the prompt-v2 dev run ran mostly on gpt-oss-20b because the 120b daily quota ran out, so its delta is inconclusive.
- **Holdout not run:** the held-out adversarial set was never executed, for lack of quota. It is not part of the submission.
- **Remaining behaviour failures:**
  - omitted policy consequences (GROUNDING_MISS);
  - skipped own-order lookups when a message also contains injected text (ROUTE_MISS);
  - occasional over-refusal.
- **Cost:** measured ≈3× over the $0.0005/question budget at Gemini Flash-Lite list prices, uncached ([ADR-3](DECISIONS.md)).

## What I'd do next
**Production deployment** (none of this is implemented):
- **Serving and scaling:** a stateless service with bounded concurrency. `answer_case` is already a pure per-case function.
- **Security:** a secret manager for keys; authenticated sessions that supply `user_id`, replacing the harness field; per-user rate limits and a spend cap.
- **Cost and resilience:** prompt caching or retrieval to reach the cost budget; a second provider with separate capacity.
- **Observability:** structured logs and metrics from the existing traces (latency, tokens, safe-failure and escalation rates) with alerting.
- **Delivery:** CI running the offline tests and a secret scan, with a scheduled golden/adversarial eval as a regression gate.

**Web user interface:**
- A thin API adapter (e.g. FastAPI) and a small chat UI over the unchanged core (`answer_case`, tools, validator). The CLI contract `python3 run_cases.py <cases.jsonl> <answers.jsonl>` stays supported.
