# Reviewer Guide

Detailed setup, execution, evaluation and navigation notes. The short entry point is [`README.md`](../README.md).

## 1. Clean-environment setup
Requires **Python 3.12**. The project is not deployed anywhere; the only network calls go to the configured LLM provider.

```bash
# Option A — uv (uses the lockfile; includes pytest and ruff)
uv sync --locked

# Option B — pip
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest ruff
```

## 2. Configuration
```bash
cp .env.example .env        # edit it: set ONE provider and its key
set -a; . ./.env; set +a    # or prefix commands with: uv run --env-file .env
```

| Provider | `LLM_PROVIDER` | Key variable (the only one read) | Models (defaults) |
|---|---|---|---|
| GroqCloud (used for the final runs) | `groq` | `GROQ_API_KEY` | `openai/gpt-oss-120b`, fallback `openai/gpt-oss-20b` |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` | `gemini-3.5-flash-lite`, fallback `gemini-3.1-flash-lite` |
| Offline fake (no key) | `fake` | — | fixed stub answer; exercises the contract and pipeline only |

- Keys are never logged, traced or written to run files. Run configs record only a 12-hex SHA-256 fingerprint.
- An inherited `GEMINI_API_KEY` is deliberately ignored.
- Optional overrides are listed, commented out, in `.env.example`.

## 3. Run the contract
```bash
python3 run_cases.py cases/golden_visible.jsonl out/answers.jsonl      # visible cases
python3 run_cases.py cases/adversarial_dev.jsonl out/dev_answers.jsonl # our adversarial dev set
LLM_PROVIDER=fake python3 run_cases.py cases/golden_visible.jsonl out/answers.jsonl   # offline smoke
```

Each run writes three files:
- `out/answers.jsonl`: one `{id, route, answer}` line per input, with `route ∈ {policy, tool, both, escalate}`.
- `out/answers.trace.jsonl`: per case — tool calls, validator verdicts, route inputs, tokens, latency, provider error detail.
- `out/answers.config.json`: models, `PROMPT_VERSION`, retry/pacing settings and the credential fingerprint.

**Exit codes:**
- `0` — every line was written.
- `2` — config or input error (e.g. a missing key); nothing is written.
- `3` — an auth/billing failure. All lines are still written as safe escalations.

## 4. Score, test, lint
```bash
python3 evals/score.py cases/golden_visible.jsonl out/answers.jsonl --trace out/answers.trace.jsonl --out out/score.md
python3 -m pytest -q                      # 724 offline tests (fake LLM, no network)
ruff check . && ruff format --check .
sha256sum -c assessment/SHA256SUMS        # the provided materials are byte-identical copies
```

**Scoring:**
- `must_include` / `must_not_include` are matched as case-insensitive regexes, plus an exact route match.
- Results are reported per set and per category, with failure-taxonomy labels. Labels marked "confirm" need manual review (see [`ITERATION.md`](../ITERATION.md) §4).

## 5. Evaluation artifacts
Every run folder under [`evals/runs/`](../evals/runs/) has `golden/` and `adversarial_dev/` subfolders. Each contains:
- `answers.jsonl`
- `trace.jsonl`
- `config.json`
- `score.md` (the most readable entry point)
- `score.json`

Each run folder also has a `NOTES.md` with the diagnosis. Runs are never edited.

| Run | What it tests | Entry point |
|---|---|---|
| 001 baseline (**first run**) | Gemini, prompt v1 | [`NOTES.md`](../evals/runs/001_baseline/NOTES.md), [`golden/score.md`](../evals/runs/001_baseline/golden/score.md) |
| 002 | Iteration 1: overload failover | [`NOTES.md`](../evals/runs/002_resilience/NOTES.md) |
| 003 | Same code; provider partially recovered | [`NOTES.md`](../evals/runs/003_rerun_provider_recovering/NOTES.md) |
| 004 | Provider move to Groq, prompt v1 | [`NOTES.md`](../evals/runs/004_groq_prompt_v1/NOTES.md), [`golden/score.md`](../evals/runs/004_groq_prompt_v1/golden/score.md) |
| 005 (**final run**) | Prompt v2 (iteration 2) + adapter fixes | [`NOTES.md`](../evals/runs/005_groq_prompt_v2/NOTES.md), [`golden/score.md`](../evals/runs/005_groq_prompt_v2/golden/score.md) |

The ADR measurements (tokens, cost, latency, label counts) come from runs 003–005 and are traced in [`DECISIONS.md`](../DECISIONS.md) and [`ITERATION.md`](../ITERATION.md).

## 6. Provider caveats and troubleshooting
- **Groq free plan:**
  - Limits are 8K tokens/min and 200K tokens/day per model. The client paces calls, so a full run takes several minutes.
  - `CASE_DEADLINE_S` defaults to 180 s when pacing is on.
  - When a model's daily quota runs out, calls fail over to the other model; the trace shows `quota_daily`.
- **Gemini:** runs 001–003 met a provider-wide 503/504 overload incident. It is recorded in [`ITERATION.md`](../ITERATION.md) §1, separately from behaviour failures.
- **Everything ends in the same "can't complete this request right now" answer:** check the `error_class` and `detail` fields in the trace. Typical causes are a missing or invalid key (exit `3`), exhausted quota, or provider overload.
- **`ConfigError` at start-up:** the key variable for the selected provider is not set.

## 7. Repository map
| Path | Contents |
|---|---|
| [`src/support_agent/`](../src/support_agent/) | Agent loop, scoped read-only tool, prompts, guards/validator, LLM adapters (Gemini, Groq, fake), config, trace |
| [`run_cases.py`](../run_cases.py) | CLI contract |
| [`data/`](../data/), [`cases/`](../cases/), [`assessment/`](../assessment/) | Provided policies/orders/visible cases; our adversarial dev set; official brief + provenance manifest |
| [`tests/`](../tests/) | Offline test suite |
| [`evals/`](../evals/) | Scorer and run artifacts |
| [`specs/`](../specs/) | Requirements (SEZ/OWN/SEC), assumptions, architecture, security, evaluation, tasks |
| [`DECISIONS.md`](../DECISIONS.md), [`decision-log.md`](decision-log.md) | The 3 ADRs; supplementary owner decisions |
| [`PROMPTS.md`](../PROMPTS.md), [`planning/prompts/`](planning/prompts/), [`system-prompts/`](system-prompts/) | Build prompts (verbatim) and in-system prompts |
| [`reviews/`](reviews/) | Independent Codex reviews and their resolution |
| [`SUBMISSION_MANIFEST.md`](../SUBMISSION_MANIFEST.md) | What the submission archive contains and excludes |
