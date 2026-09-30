# Submission Manifest

Based on `assessment/PROMPT.md` ("Deliverables") and `assessment/SUBMISSION.md`: a zip of the project *or* a private repo shared with the reviewer; don't post publicly. The zip is produced from the committed tree with `git archive`, so untracked and git-ignored files are excluded by construction. Paths marked `export-ignore` in `.gitattributes` are also left out.

## REQUIRED — explicitly required by the assessment
| Item | Path | Source of the requirement |
|---|---|---|
| Code | `src/support_agent/` | PROMPT.md Deliverables 1 |
| CLI contract | `run_cases.py` | PROMPT.md "The one contract" |
| Exactly 3 decision records | `DECISIONS.md` | Deliverables 2 |
| Iteration evidence: first and final run + note | `evals/runs/001_baseline/` (first), `evals/runs/005_groq_prompt_v2/` (final), `ITERATION.md` (note) | Deliverables 3 |
| Build prompts + in-system prompts | `PROMPTS.md`, `docs/planning/prompts/`, `docs/system-prompts/` | Deliverables 4 |
| How to run + unfinished | `README.md` | Deliverables 5 |
| Data the contract reads at runtime | `data/policies/*.md`, `data/orders.json` | Needed for `run_cases.py` to run (the provided package's data) |

## RECOMMENDED — reproducibility and review
| Item | Path |
|---|---|
| Dependencies (locked) | `pyproject.toml`, `uv.lock`, `requirements.txt` |
| Env template (no secrets) | `.env.example` |
| Visible cases + our adversarial dev set | `cases/golden_visible.jsonl`, `cases/adversarial_dev.jsonl` |
| Offline tests (724, fake LLM) | `tests/` |
| Scorer | `evals/score.py`, `evals/README.md` |
| Intermediate runs (incident, iterations) | `evals/runs/002_resilience/`, `evals/runs/003_rerun_provider_recovering/`, `evals/runs/004_groq_prompt_v1/` |
| Specs (requirements, assumptions, architecture, security, evaluation, tasks) | `specs/` |
| Decisions, reviews, agent process | `docs/decision-log.md`, `docs/reviews/`, `docs/agent-plan.md`, `docs/implementation-prompts.md`, `docs/readiness-checklist.md`, `AGENTS.md`, `CLAUDE.md` |
| Planning research and smoke tests (evidence of how AI tools were directed) | `docs/planning/research/`, `docs/planning/smoke-test/`, `docs/planning/STACK_DECISION_MATRIX.md` |
| Official inputs + provenance | `assessment/PROMPT.md`, `assessment/SUBMISSION.md`, `assessment/MANIFEST.md`, `assessment/SHA256SUMS` |
| Detailed setup/run/evaluation guide | `docs/REVIEWER_GUIDE.md` |
| This manifest | `SUBMISSION_MANIFEST.md` |

## EXCLUDE
| Item | Why | How it is excluded |
|---|---|---|
| `.env`, API keys, credentials | Secrets | git-ignored, never committed |
| `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `out/`, `*.zip` | Local caches and outputs | git-ignored / untracked |
| IDE files (`.idea/`, `.vscode/`) | Local | git-ignored |
| Agent worktrees, orchestrator state, tmux sessions | Development-only tooling outside the repo | never inside the repo |
| Held-out adversarial cases | Kept outside the repo to prevent overfitting; never run; not required by the assessment | outside the repo |
| `docs/planning/ADVISORY_REPORT.md` | Internal pre-implementation advisory, written in Spanish at the owner's request, with local capacity/scheduling details. Kept in the repo history | `.gitattributes` export-ignore |
| `docs/planning/PROMPT_LOG.md` | Pre-repository prompt log, superseded by `PROMPTS.md` (same records). Kept in the repo history | `.gitattributes` export-ignore |

## Create the zip
```bash
git archive --format=zip --prefix=sezzle-support-agent/ -o ../sezzle-support-agent.zip HEAD
```
