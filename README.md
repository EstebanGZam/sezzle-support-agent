# Sezzle Support Agent

**Author:** Esteban Gaviria Zambrano

An LLM shopper-support assistant. It answers from the 12 policies, looks up the caller's own orders through one read-only, user-scoped tool, and escalates human-only matters. The LLM writes every answer; code enforces authorization, output validation and safe failure.

> Focused implementation and evaluation time: approximately 2h 15m (tracked independently).

## Run
Python 3.12. Install with `uv sync --locked` (or `pip install -r requirements.txt`). Then copy `.env.example` to `.env`, set `LLM_PROVIDER=groq` and `GROQ_API_KEY` (or `gemini` + `GOOGLE_API_KEY`), and load it with `set -a; . ./.env; set +a`.
```bash
python3 run_cases.py <cases.jsonl> <answers.jsonl>       # e.g. cases/golden_visible.jsonl out/answers.jsonl
```
The [Reviewer Guide](docs/REVIEWER_GUIDE.md) covers offline mode, tests, scoring, traces, provider caveats and the repository map.

## Deliverables
| Required | Where |
|---|---|
| Code + contract | [`run_cases.py`](run_cases.py), [`src/support_agent/`](src/support_agent/) |
| 3 decision records | [`DECISIONS.md`](DECISIONS.md) |
| First run (visible cases) | [`evals/runs/001_baseline/golden/score.md`](evals/runs/001_baseline/golden/score.md) · [`answers`](evals/runs/001_baseline/golden/answers.jsonl) · [notes](evals/runs/001_baseline/NOTES.md) |
| Final run (visible cases) | [`evals/runs/005_groq_prompt_v2/golden/score.md`](evals/runs/005_groq_prompt_v2/golden/score.md) · [`answers`](evals/runs/005_groq_prompt_v2/golden/answers.jsonl) · [notes](evals/runs/005_groq_prompt_v2/NOTES.md) |
| What failed, what changed, why | [`ITERATION.md`](ITERATION.md): "At a glance" first; all runs in [`evals/runs/`](evals/runs/) |
| Build + in-system prompts | [`PROMPTS.md`](PROMPTS.md) |

## Honestly unfinished
- **Runs 001–003** hit a Gemini-wide overload incident. The final runs use Groq's free plan, whose daily quota limited reruns.
- **Final visible-case run (005)** predates two adapter-only error-handling fixes and was not rerun.
- **Prompt-v2 dev set** ran mostly on the 20b fallback, so its delta is inconclusive.
- **Held-out adversarial set** was never executed.
- **Remaining failures:** omitted policy consequences and skipped own-order lookups.
- **Cost:** ≈3× over the $0.0005/question budget without caching ([ADR-3](DECISIONS.md)).

## What I'd do next
1. **Production:** productionize and securely deploy the assistant (secrets, authenticated sessions, rate/spend limits, monitoring, CI).
2. **Web/API layer:** add a thin web/API layer and UI over the same agent core. The CLI contract stays.

Neither is implemented.
