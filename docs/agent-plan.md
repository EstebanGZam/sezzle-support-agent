# Agent Plan — roles, isolation, review gates

Owner-approved structure (OD-10). The Orchestrator lead coordinates; the owner approves. This plan describes *development* agents only; the support assistant's own LLM (Gemini) is a separate component with separate billing.

## Components (kept distinct)
| Component | What it is | Auth / billing |
|---|---|---|
| Orchestrator lead | Claude Code session running `orchestrator` (v0.5.4); coordinates, owns specs & integration | Claude subscription |
| Principal implementer (IMP) | Claude Code teammate (headless dispatch) in its own git worktree | Claude subscription |
| Evaluation agent (EVAL) | Claude teammate in a separate worktree; owns `evals/`, case sets, eval runs | Claude subscription |
| Independent reviewer (REV) | Codex CLI, read-only review; different provider from the implementer | ChatGPT/Codex subscription |
| Claude Cloud | Optional; not on the critical path (Orchestrator cannot launch/track cloud sessions — verified) | Claude cloud-session credit (unverified promo) |
| Support-assistant LLM | Gemini API, called by application code | Google project billing — **must be paid tier** (A-10) |

## Responsibilities (RACI-lite)
| Activity | LEAD | IMP | EVAL | REV | OWNER |
|---|---|---|---|---|---|
| Requirements, assumptions, ADR wording | R | — | C | C | **A** |
| Architecture/spec changes | R | proposes | proposes | proposes | **A** |
| Implementation T-01..T-11 | coordinates, lands | **R** | — | — | informed |
| Eval harness T-18, case sets, runs T-13/T-14 | coordinates | fixes code | **R** | — | informed |
| Code/security review T-12 (and per-merge spot reviews) | integrates findings | fixes | — | **R** | decides disputes |
| Iteration hypotheses | R (proposes) | implements | measures | — | **A** for scope-changing ones |
| Docs T-15/T-16, delivery T-17 | **R** | — | C | C | **A** |

## Isolation & integration protocol
- **Branches:** `main` is the stable branch. IMP works on `feat/impl` in an orchestrator worktree; EVAL on `feat/evals` in its own worktree. **Disjoint files** per `specs/tasks.md`.
- **Git repo required:** Codex refuses to run outside a git repository ("Not inside a trusted directory"). All dispatches use worktrees or the repo root.
- **Landing:** after the verification commands pass in the worktree, `orchestrator land <role> --dry-run` (the LEAD reviews the diff), then `orchestrator land <role>`. Never merge untested agent code. No force-push to `main`.
- **Review gate:** REV reviews every landing that touches `agent.py`, `tools.py`, `guards.py`, `prompts.py`, or `llm/`. Findings go to `docs/reviews/R-NN.md`.
- **Implementer ≠ reviewer**, always.
- **Capacity:** before each dispatch wave, run `orchestrator usage` + `orchestrator providers`. On a quota/rate-limit failure, do cross-provider failover per the owner's global policy: preserve the worktree, then hand off to another allowed provider (claude/codex/agy/opencode) with "continue, don't restart". Compile or test failures are **not** quota failures.
- **Shutdown:** every teammate is shut down as soon as its task lands.

## Prompt traceability
- Every dispatch's exact task text is saved from `~/.local/state/agent-team/projects/<project>/<role>/task.md` into `docs/planning/prompts/agents/` and indexed in `PROMPTS.md` with: ID, purpose, agent, exact prompt, context, expected, observed, files, commit, follow-up.
- In-system prompts are versioned by `PROMPT_VERSION` (hash) and recorded in `PROMPTS.md` §System prompts at every change.
- Eval prompts, if any (e.g. manual review rubrics), go in `PROMPTS.md` §Evaluation prompts.

## Claude Cloud (optional)
Only if the owner opts in:
1. Push the private repo.
2. Install the Claude GitHub App on that repo only.
3. `claude --cloud "<IP-xx prompt>"` for one bounded, disjoint task (candidate: E-01 score.py, or a second-opinion review).
4. Review the PR locally with `gh pr checkout`; land only after tests pass.

Keep sessions **Private**. Log the prompt in PROMPTS.md.
