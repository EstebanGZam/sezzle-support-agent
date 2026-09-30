# Implementation-Readiness Checklist (final)

Updated after the owner's decisions (P-005). Implementation (IP-01, E-01) starts only on explicit owner authorization (OD-23).

## A. Specification package — complete
- [x] Assessment materials in the documented layout, byte-identical, with provenance manifest; `sha256sum -c assessment/SHA256SUMS` passes (16/16); originals untouched.
- [x] `AGENTS.md` (single source) + `CLAUDE.md` (`@AGENTS.md`).
- [x] `specs/requirements.md` — SEZ (official) / OWN (owner) / SEC separated, with acceptance criteria and verification; level expectations SEZ-L01..L03.
- [x] `specs/assumptions.md` — 17 assumptions; A-10 revised with the original observation preserved.
- [x] `specs/architecture.md` — canonical contracts (answer schema with `policy_applied`, route rule, error/retry table, `PROMPT_VERSION`, config defaults, key source).
- [x] `specs/security.md` — OWASP mapping, tripwire (4 categories), typed-claim validator with required fixtures, safe failure, hygiene.
- [x] `specs/evaluation.md` + `cases/adversarial_dev.jsonl` (25). Holdout (15) and its index are kept outside the repo; the holdout-naming prompt copy is redacted.
- [x] `specs/tasks.md` — T-01…T-18, traceability matrix, scope tiers and cut order.
- [x] `DECISIONS.md` — 3 ADRs in the required format; model IDs filled in; `[MEASURE]` placeholders remain until real runs.
- [x] `docs/decision-log.md` — OD-01…OD-23 (owner) vs AR-01…AR-09 (agent), with a status for each.
- [x] Independent review R-00 (Codex): 13 findings, resolved (`docs/reviews/R-00-resolution.md`).
- [x] Credential-provenance investigation (`docs/reviews/credential-provenance.md`).
- [x] Every owner and agent prompt preserved (`PROMPTS.md`, `docs/planning/prompts/`).

## B. Environment & credentials
- [x] Toolchain: uv 0.11.8 (provisions Python 3.12), `gh` authenticated, orchestrator 0.5.4.
- [x] Model availability (`models.list`) and compatibility (S-001): `gemini-3.5-flash-lite` ✓, `gemini-3.1-flash-lite` ✓ (tools + JSON schema in one call); `gemini-2.5-flash-lite` ✗.
- [x] Inference availability confirmed: agent-side (15× HTTP 200) and owner-side (`gemini-3.8-flash`, HTTP 200).
- [ ] **Owner, before the first real run (T-13) — not before IP-01:** place the key you manage in `.env` as `GOOGLE_API_KEY`, and confirm its project's data-handling terms (SEC-14). Optional: compare its fingerprint with `53408af16a25` to see whether it is the key the agents used.
- [ ] Recommended, non-blocking: `tmux set-environment -gu GEMINI_API_KEY`. This stops agent panes from inheriting a key; the application already ignores it (AR-09).
- [ ] Recommended, non-blocking: disable non-development MCP connectors for the build session.
- [ ] Non-blocking: orchestrator reinstall-from-source update notice.

## C. Model smoke test (S-001) — historical evidence, unchanged
Synthetic content only; n = 3 per model; tiny prompts.

| Model | Tool call | Tools + JSON schema (turn 2) | 2-call latency, median (range) |
|---|---|---|---|
| `gemini-3.5-flash-lite` | 3/3 | 3/3 | 2.67 s (2.00–2.74) |
| `gemini-3.1-flash-lite` | 3/3 | 3/3 | 3.04 s (2.97–3.77) |
| `gemini-2.5-flash-lite` | 3/3 | 0/3 (unsupported combination) | — |

Cache probe: 429 on the free-tier *cache-storage* quota (limit 0). Revised interpretation in A-10: inference is unaffected, billing is unverified, and caching is not required.

## D. Owner decisions — status
| Item | Status |
|---|---|
| Models (OD-15), no automatic unpaid switch (OD-16), no 2nd provider (OD-17) | ✅ decided |
| Architecture (OD-18) | ✅ approved |
| AR-02, AR-03, AR-07, AR-08 | ✅ provisionally approved |
| AR-01 (≤1 tool round), AR-04 (neutral facts), AR-05 (holdout outside repo) | Applied as defaults (consistent with OD-18/OD-12). Override at authorization if you disagree |
| AR-09 (key only from `GOOGLE_API_KEY`, fingerprint in run config) | Proposed; applied as the default. Override at authorization if you disagree |
| Contested route labels (A-08 foreign/nonexistent → `tool`, A-09 out-of-scope → `policy`, A-15 human request → `escalate`) | Documented assumptions; eval reports them as CONTESTED |
| Claude Cloud | Optional, off the critical path (OD-21) |
| Deployment | Deferred (OD-22) |

## E. Delivery checks (T-15…T-17)
- [ ] `grep -c '^## ADR-' DECISIONS.md` = 3; each ADR has Decision / Options / Why / Would change my mind; no `[MEASURE` left.
- [ ] First (`001_*`) and final runs committed unedited; `ITERATION.md` has taxonomy, deltas and the holdout result.
- [ ] `PROMPTS.md` has planning, agent, system (with `PROMPT_VERSION`) and eval sections.
- [ ] `README.md` ≤ ~35 lines: run instructions, env vars, "Unfinished", key assumptions (A-04, A-08, A-10).
- [ ] The zip from `git archive` runs `uv sync --locked && uv run pytest -q` in a temp dir; `sha256sum -c` passes; no `.env`.

## F. Gate before creating the private remote / first push (OD-20)
- [ ] gitleaks (full history) clean; `grep -rE 'AIza|sk-'` clean across repo and history.
- [ ] No `.env`; traces and `config.json` contain only credential fingerprints, never values.
- [ ] The holdout is either still outside the repo, or committed only together with the final run.
- [ ] Owner confirms repo visibility = **private** and the reviewer to share with.

## G. Genuine blockers
1. **Explicit owner authorization to start implementation (OD-23).** This is the only blocker for IP-01/E-01.
2. **Owner-managed `GOOGLE_API_KEY` + data-handling confirmation.** This blocks only the first real LLM run (T-13), not implementation.
3. **§F checks.** These block only the creation of the remote repo / push.
