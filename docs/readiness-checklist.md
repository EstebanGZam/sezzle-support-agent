# Implementation-Readiness Checklist

Implementation (IP-01 onward) starts only when every **blocking** item is checked and the owner explicitly authorizes it.

## A. Specification package
- [x] Assessment materials copied into the documented layout with a provenance manifest; `sha256sum -c assessment/SHA256SUMS` passes (16/16).
- [x] Originals untouched in `~/Documents/Sezzle/sezzleaiengineertakehomechallenge/`.
- [x] `AGENTS.md` (single source) + `CLAUDE.md` (`@AGENTS.md`).
- [x] `specs/requirements.md` — SEZ / OWN / SEC separated, acceptance criteria + verification.
- [x] `specs/assumptions.md` — 17 assumptions with evidence, rationale, risk, impact.
- [x] `specs/architecture.md` — modules, contracts, loop, deterministic/LLM boundary, errors, config, concurrency path.
- [x] `specs/security.md` — trust boundaries, OWASP mapping, tripwire, validator checks, safe failure, hygiene.
- [ ] `specs/evaluation.md` + `cases/adversarial_dev.jsonl` + holdout outside the repo — *evaluation agent (A-010)*.
- [x] `specs/tasks.md` — T-01…T-18 with requirement traceability and file ownership.
- [x] `DECISIONS.md` — 3 proposed ADRs in the required format, with `[MEASURE]` placeholders.
- [x] `docs/decision-log.md` — owner decisions vs agent recommendations.
- [x] `docs/agent-plan.md`, `docs/implementation-prompts.md`, `PROMPTS.md`, `.gitignore`, `.env.example`.
- [x] Independent review of this package (Codex, A-011 → `docs/reviews/R-00-spec-package.md`): 1 blocker + 11 major + 1 minor findings. Resolution per finding in `docs/reviews/R-00-resolution.md`. The only remaining blocker is the owner's model decision (OD-15).

## B. Environment (verified 2026-09-27)
- [x] Python 3.13 system / uv 0.11.8 available (uv will provision 3.12 for the project); `gh` authenticated; orchestrator 0.5.4.
- [x] Gemini models available via `models.list`: `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite` (+ 2.5, which is incompatible with tools + JSON schema).
- [ ] **BLOCKING — Gemini billing:** the current key's project is on the **free tier** (smoke-test evidence, A-10). Enable billing on that project (AI Studio → project → Billing) or provide a billed key, and set a budget alert (~$10). Needed before any real run with assessment material (SEC-14).
- [ ] Orchestrator update: `orchestrator update --check` asks for a one-time reinstall from its original source (non-blocking).
- [ ] Disable non-development MCP connectors for the build session (Slack, Miro, Shopify, Tally, Eraser, Atlassian, Gmail, Drive, Calendar, Notion, Figma, pencil…) — non-blocking, recommended.
- [ ] Optional: add the official Gemini Docs MCP (read-only).

## C. Model smoke test (S-001, synthetic content only, n = 3 per model)

| Model | Tool call | Tools + JSON schema (turn 2) | Thought signature | 2-call latency (median of 3) | Price in/out per 1M (pricing page, 2026-09-24) |
|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 3/3 | 3/3 valid | yes | **2.67 s** (2.00–2.74) | $0.30 / $2.50 |
| `gemini-3.1-flash-lite` | 3/3 | 3/3 valid | yes | 3.04 s (2.97–3.77) | $0.25 / $1.50 |
| `gemini-2.5-flash-lite` | 3/3 | **0/3 — "Function calling with a response mime type: 'application/json' is unsupported"** | no | — | $0.10 / $0.40 (limited access) |

- **Caveats:** tiny prompts (≈125–210 input tokens), free-tier project, n = 3, so treat the latencies as indicative only. `thoughtsTokenCount` was absent at `minimal` thinking. Explicit caching could not be tested (free-tier limit 0).
- **Implication:** only the **3.x Flash-Lite** models are compatible with the planned loop, and each is the other's natural fallback.

## D. Decisions requiring owner approval
1. **OD-15 — Lock the primary/fallback model (blocking IP-01; config has no default).**
   - *Recommendation:* `gemini-3.5-flash-lite` primary, `gemini-3.1-flash-lite` fallback. 3.5 was faster in the smoke test, and Google recommends it for new projects.
   - *Alternative:* 3.1 primary. It is 17 % cheaper on input and 40 % cheaper on output, which gives the cost ADR more headroom.
   - Either choice can be reversed via env.
2. **Gemini billing (blocking for real runs, T-13):** enable billing on the key's project or provide a billed key, and set a budget alert (A-10).
3. **Approve, change or reject the AR bundle** (AR-01…AR-08 in `docs/decision-log.md`). The most consequential items:
   - the `policy_applied` route signal (AR-02);
   - the neutral-facts boundary (AR-04);
   - the expanded tripwire (AR-07);
   - the scope tiers (AR-08).
4. **Contested route labels:** foreign/nonexistent order → `tool` (A-08); out-of-scope → `policy` (A-09); explicit request for a human → `escalate` (A-15).
5. **Remote repository:** create the private GitHub repo now (enables CI and optional Claude Cloud), or stay local until delivery.
6. **Claude Cloud:** use it for one bounded task, or skip.
7. **Authorize implementation start** (IP-01, and E-01 in parallel).

## E. Delivery checks (T-15…T-17)
- [ ] `grep -c '^## ADR-' DECISIONS.md` = 3; each ADR has Decision / Options / Why / Would change my mind; no `[MEASURE` left.
- [ ] `evals/runs/001_*` (first run) and the final run committed unedited; `ITERATION.md` has failure taxonomy + deltas + holdout result.
- [ ] `PROMPTS.md` has planning, agent, system (with `PROMPT_VERSION`) and eval sections.
- [ ] `README.md` ≤ ~35 lines: run instructions, env vars, "Unfinished", key assumptions (A-04, A-08, A-10).
- [ ] `sha256sum -c assessment/SHA256SUMS` passes; gitleaks clean; no `.env` in the archive.
- [ ] Zip from `git archive` runs `uv sync --locked && uv run pytest -q` in a temp dir.
