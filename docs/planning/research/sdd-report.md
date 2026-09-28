# Process & tooling for a 2-hour AI-assisted take-home (research, 2026-09-27)

Legend: **[V]** = verified against the cited source today; **[U]** = unverified / assumption.

## Part 1 — SDD tool choice

| | GitHub Spec Kit | OpenSpec | Plain `specs/*.md` + `AGENTS.md` |
|---|---|---|---|
| Install | `uv tool install specify-cli` + `specify init --integration <key>`; Python 3.11+ [V: github.com/github/spec-kit] | `npm i -g @fission-ai/openspec`; Node ≥ 20.19 [V: github.com/Fission-AI/OpenSpec] | None |
| Generated footprint | `.specify/` (constitution, templates, scripts) plus skills in `.claude/skills` (Claude) and `.agents/skills` (Codex) [V: github.github.io/spec-kit/reference/integrations.html] | `openspec/specs`, `openspec/changes/<id>/{proposal,design,tasks}.md` + spec deltas, its own AGENTS.md guidance [V: repo README] | 2–3 files you write yourself |
| Context overhead | High: constitution → spec → plan → tasks → implement, each producing long artifacts | Medium: propose → apply → archive | Minimal, and you control it |
| Claude Code / Codex | Both are supported. Claude uses `/speckit-*`, Codex uses `$speckit-*`. A project can hold several integrations only if Spec Kit marks them "multi-install safe", otherwise you need `--force` [V: integrations page] | Claims "30+ tools" including Claude. I did not confirm Codex on the README excerpt [U] | Native: Codex reads AGENTS.md, and Claude reads AGENTS.md directly or through `@AGENTS.md` [V, Part 2] |
| tmux orchestrator | Slash-skills depend on the agent. Teammates on different providers invoke them differently, and the ceremony has to happen in order | Same issue, smaller | Any agent can be told "implement R3 in specs/requirements.md". No tooling dependency |
| Fit for ~2h | Poor. Setup and ceremony take roughly 20–30 min [U, estimate], and the brief doesn't grade scaffolding | Fair, but it's still a new tool to learn under time pressure | **Best** |

**Recommendation:** use plain repo-native Markdown specs. The grader values design decisions, the iteration loop and grounding. Tool ceremony isn't graded (the brief says "Scaffolding quality… NOT graded"), and each extra tool adds a new way to fail on the clock.

### Minimal spec file set (does not duplicate the brief's required files)
The brief already requires README.md, DECISIONS.md (3 ADRs), PROMPTS.md, run_cases.py and the eval runs, so the specs **link to** those files and never restate them.

```
AGENTS.md                 # agent operating rules (≤60 lines)
CLAUDE.md                 # one line: @AGENTS.md  (+ optional Claude-only notes)
specs/requirements.md     # R-IDs + acceptance criteria + verification
specs/tasks.md            # ordered task checklist mapped to R-IDs, owner, status
```
Stick to these two spec files. Skip `design.md`: design lives in DECISIONS.md, and a second copy would only drift.

**Template: `specs/requirements.md`**
```markdown
# Requirements (source of truth for behavior; design rationale -> DECISIONS.md)
Contract: see run_cases.py docstring (do not restate here).

## R1 Routing
Statement: Every case gets route ∈ {policy, tool, both, escalate}.
Acceptance:
- AC1.1 Output line per input id, valid JSON, route in enum.
- AC1.2 Unknown/malformed model output -> route=escalate (fail closed).
Verify: `uv run pytest tests/test_routing.py`; eval: `python3 run_cases.py cases/dev.jsonl out.jsonl`
Status: todo | doing | done | cut (reason)

## R2 Grounded policy answers  (cite doc ids; no answer without retrieved chunk)
## R3 Account/order tools      (user_id-scoped; model can't pass another user's id)
## R4 Escalation               (refunds/disputes/PII/other-user -> escalate)
## R5 Budget/latency           (see ADR-2; measure p95 + $/1k in eval)
## NFR  No secrets in repo; LLM mocked in CI.
```
**Template: `specs/tasks.md`**
```markdown
| ID | Task | Req | Owner(agent) | Verify cmd | Status |
|----|------|-----|--------------|------------|--------|
| T1 | Loader for docs+accounts | R2,R3 | codex-impl | pytest -k loader | done |
```
Put the `Status: cut (reason)` lines straight into README's "unfinished" section. Honesty about what was cut is graded positively.

## Part 2 — AGENTS.md vs CLAUDE.md (avoid duplicate/contradictory instructions)

- **Claude Code** [V: code.claude.com/docs/en/memory]:
  - Recent versions (v2.1.277+) read `AGENTS.md` natively, but *by default only when no CLAUDE.md/CLAUDE.local.md exists* in the cwd or above. If both exist, Claude reads "Your CLAUDE.md files only".
  - A `CLAUDE.md` containing `@AGENTS.md` is officially supported, and it "never makes Claude read AGENTS.md twice".
  - Imports recurse up to 4 hops. Aim for less than 200 lines per file.
  - "If two rules contradict each other, Claude may pick one arbitrarily."
  - `CLAUDE.local.md` counts as a CLAUDE.md, so creating one silently disables native AGENTS.md loading.
- **Codex** [V: learn.chatgpt.com/docs/agent-configuration/agents-md, redirected from developers.openai.com]:
  - Loads global `~/.codex/AGENTS(.override).md` first.
  - Then walks from the git root down to the cwd, taking at most one file per directory (`AGENTS.override.md` > `AGENTS.md` > fallback names).
  - Files are concatenated root→leaf, so later files win. The cap is `project_doc_max_bytes` = 32 KiB.
- **agents.md** [V: agents.md]: plain Markdown with no required fields. "Closest AGENTS.md wins; explicit user chat prompts override everything." The site suggests symlinks when migrating from other filenames.

**Rule to adopt:**
- AGENTS.md is the single source of truth.
- CLAUDE.md is exactly `@AGENTS.md` plus, optionally, a small "Claude-only" section: tool/permission notes that never restate or contradict AGENTS.md. Keeping the import also covers sessions where native AGENTS.md loading is off.
- Don't use CLAUDE.local.md, and don't add nested AGENTS.md files.
- Keep AGENTS.md short: commands, rules, pointers to `specs/`.
- Watch the user's global `~/.claude/CLAUDE.md` (orchestrator lead-mode rules). It loads alongside the project file, so the project AGENTS.md should not restate orchestration policy.

## Part 3 — Git / GitHub

- **Commits:** Conventional Commits 1.0.0: `<type>[scope]: <desc>`. `feat` = MINOR and `fix` = PATCH. Mark breaking changes with `!` or a `BREAKING CHANGE:` footer. Other listed types: build, chore, ci, docs, style, refactor, perf, test [V: conventionalcommits.org/en/v1.0.0]. Suggested scopes: `router`, `tools`, `retrieval`, `eval`, `docs`.
- **Branches:** short-lived `feat/<R-id>-slug`, one per orchestrator worktree, squash- or fast-forward-merged into `main` within about 30 min. Each merge is gated on local `ruff` + `pytest` passing.
- **Branch protection on a private repo with a free personal account: NOT available.**
  - GitHub's plans page lists "Protected branches" and "Required pull request reviewers" for *private repositories* under **GitHub Pro** [V: docs.github.com/en/get-started/learning-about-github/githubs-plans].
  - The rulesets page scopes them to Team/Enterprise in the fetched text [V: docs.github.com/.../about-rulesets]. Public repos on Free do get them, but a public repo is off-limits here because the brief says not to post publicly.
  - → Don't buy Pro for this. Rely on the orchestrator's land step plus CI as the gate, and write that down.
- **Actions quota:** Free includes 2,000 min/month for private repos [V: plans page]. The CI below needs about 1 min per run [U, estimate].
- **Minimal CI** (`.github/workflows/ci.yml`). Pins follow the uv guide (setup-uv v9, checkout v7) [V: docs.astral.sh/uv/guides/integration/github]. gitleaks-action v3 needs no license for personal-account repos [V: github.com/gitleaks/gitleaks-action]:
```yaml
name: ci
on: [push, pull_request]
permissions: { contents: read }
jobs:
  test:
    runs-on: ubuntu-latest
    env: { LLM_PROVIDER: fake }          # mocked LLM; no secrets in CI
    steps:
      - uses: actions/checkout@v7
        with: { fetch-depth: 0 }         # gitleaks scans history
      - uses: gitleaks/gitleaks-action@v3
        env: { GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
      - uses: astral-sh/setup-uv@v9
      - run: uv sync --locked
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run pytest -q
```
  - Mock LLM: put a `FakeLLM` behind the same client interface. It returns canned structured outputs keyed by case id, and pytest uses it by default.
  - The *real* eval runs (first and final) happen locally and get committed as artifacts. This keeps CI free while the pipeline still contains a real LLM, as the brief requires.

## Part 4 — Skills / MCP for this session

**Add at most one**, and only if the pipeline uses Gemini:
- **Gemini API Docs MCP**, `https://gemini-api-docs-mcp.dev`.
  - Provenance: official, Google-hosted. Exposes `search_documentation`. No auth is mentioned [V: ai.google.dev/gemini-api/docs/coding-agents].
  - Permissions: read-only docs, so allow it.
  - Skip Google's `npx skills add google-gemini/gemini-skills …` for a 2h build: it's third-party install tooling and runs globally.
- If the pipeline uses **OpenAI**: the existing `openaiDeveloperDocs` is enough.
- If it uses **Anthropic**: Claude Code's built-in `claude-api` skill and Claude Docs are enough.
- **Context7:** skip.
  - It's maintained by Upstash, but the docs are community-contributed and it "cannot guarantee the accuracy, completeness, or security" [V: github.com/upstash/context7].
  - It also adds a supply-chain and prompt-injection surface without covering anything the official docs don't.

**Disable for the session** to save context and reduce risk:
- Claude side: Notion, Gmail, Google Drive/Calendar, Figma, Excalidraw, pencil, and the unauthenticated connectors (Expedia, Atlassian, etc.).
- Codex side: azure, terraform, aws-knowledge, microsoft-learn, livekit-docs, figma, eraser.

**Keep:**
- The provider-matching docs MCP.
- `codebase-memory-mcp`: optional, since the repo is tiny and grep is enough.
- Claude Docs: only if you need Claude Code docs.

This also avoids any risk of an agent pushing assessment material to Notion/Drive/Gmail, which the brief forbids.

## Agent execution protocol (≤15 lines, paste into AGENTS.md)
```
1 Analyze: read PROMPT/SUBMISSION, data, specs/; list ambiguities. No code.
2 Specify: add/edit R-IDs + acceptance criteria in specs/requirements.md.
3 Approve: human OKs the R-IDs/tasks before implementation (log prompt in PROMPTS.md).
4 Plan: map tasks->R-IDs in specs/tasks.md; one owner per file; one worktree per task.
5 Implement: smallest change satisfying the ACs; model never gets raw account access
  or cross-user ids; tools are deterministic, user_id injected by code.
6 Test: uv run ruff check . && uv run pytest -q (FakeLLM); add a test per AC.
7 Evaluate: python3 run_cases.py <cases> <out>; record score + failures in eval notes.
8 Review: a different agent/provider reviews the diff against ACs (implementer != reviewer).
9 Commit: Conventional Commit referencing R-ID; update task Status; never commit secrets.
Stop and escalate to the human on: contract changes, ADR-level choices, scope cuts.
```

## Recommendation
- Use plain `AGENTS.md` (single source of truth) + a `CLAUDE.md` that is just `@AGENTS.md`.
- Add `specs/requirements.md` (R-IDs/ACs/verify) and `specs/tasks.md`. No Spec Kit or OpenSpec.
- Use a private GitHub repo with Conventional Commits and short-lived worktree branches.
- CI: gitleaks → ruff → pytest, with the LLM mocked. Accept that there's no branch protection on the Free plan, and document it.
- Add only the Gemini Docs MCP, and only if you pick Gemini. Disable every non-dev MCP for the session.

## Open questions
1. Which LLM provider? That decides which docs MCP, if any, is worth adding.
2. Will the repo be under a personal account (gitleaks needs no license) or an org (a free license key is required)?
3. Should `PROMPTS.md` be filled by hand, or should the orchestrator's prompt log be exported into it?
4. Is the local Claude Code version ≥ 2.1.277? This only matters if you drop `CLAUDE.md`, and keeping the `@AGENTS.md` import makes it moot.
5. The checkout v7 / setup-uv v9 pins were taken from the uv docs page today. Re-check them on first CI run [partially U].
