# Claude Code cloud sessions for the Sezzle take-home: research report

Date: 2026-09-27. I launched nothing, installed nothing, and spent no credits. Docs pages were fetched today.
Legend: **V** = verified (source cited), **L** = verified by local inspection, **U** = unverified or my assumption.

## Local facts
- Installed Claude Code is **v2.1.283**. Auth is `claude.ai`, with `subscriptionType: "pro"`. **L** (`claude --version`, `claude auth status`)
- `claude --help` shows these cloud-related flags: `--cloud [description|session_id|url]`, `--teleport [session]`, `--environment <id>` (self-hosted only), `--from-pr`, `--remote-control`, and the `ultrareview` subcommand. The older `--remote` flag is not listed. Per the docs it still works as a deprecated alias of `--cloud`. **L/V**
- The project directory `~/Documents/Sezzle/sezzleaiengineertakehomechallenge` is **not a git repo** and has no remote. It holds 88 KB: 12 policy docs, `DATA-orders.json`, `CASES_-_golden_visible.jsonl`, `PROMPT.md` and `SUBMISSION.md`. **L**
- `gh` is logged in as `EstebanGZam` with the `repo` and `workflow` scopes. **L**

## 1) How to launch cloud tasks
Cloud sessions are available on Pro, Max and Team plans, so this Pro account qualifies. You can start one from any of these surfaces **V** ([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web)):
- **Web** at claude.ai/code, the mobile app's Code tab, or the Desktop app with "Cloud" selected.
- **CLI:** `claude --cloud "task"`. This clones the **GitHub remote at your current branch, not your local checkout**, so push first. Each call creates its own parallel session.
- **Follow-ups:** `claude -p "msg" --cloud <session-id>` queues a message and exits. With `--output-format json` it returns `{ok, session_id, url}`.
- **Repos with no remote,** or repos where the GitHub App isn't installed, get uploaded as a git bundle instead. The directory must be a git repo with at least one commit. Untracked files are excluded. Uncommitted `.env`, `*.pem` and similar files are left out. A session started from a bundle **can push back only if your GitHub connection has push access to the repo**.
- **Pulling a session back:** `claude --teleport [id]`, `/teleport`, or `/tasks` then `t`. This is **one-way, cloud→local.** You can't push an existing terminal session to the cloud from the CLI (the Desktop app has "Continue in").
- `--remote-control` is **unrelated**. It lets you steer a *local* session from your phone or browser.

## 2) Official API/SDK for launching
- **Routines API trigger:** `POST https://api.anthropic.com/v1/claude_code/routines/<trig_id>/fire` with a per-routine bearer token and the beta header `experimental-cc-routine-2026-04-01`. It returns `claude_code_session_id` and `claude_code_session_url`. It is a **research preview** and only for claude.ai users. You create the token on the web, and the CLI can't create it. The body's `text` field arrives wrapped as untrusted data. **V** ([routines](https://code.claude.com/docs/en/routines))
- I found no general "create an arbitrary cloud session" REST API. The practical programmatic surface is the CLI (`claude --cloud`, `claude -p --cloud <id>`). **U:** that no such API exists; I only confirmed it isn't in the docs index.
- The Agent SDK and `claude -p` run **locally**. They are not cloud sessions. **V** ([Agent SDK plan credit](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan))

## 3) GitHub integration triggers
- **claude-code-action (GitHub Actions):** triggered by `@claude` in issue or PR comments, reviews, or new issue title/body. With a `prompt` input it runs on any event, including `schedule` and `pull_request`. Only users with write access can trigger it, and bots are rejected by default. Setup is `/install-github-app` or manual. Auth is `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`, uses the subscription). It **runs on GitHub runners and uses Actions minutes, not cloud sessions**. **V** ([github-actions](https://code.claude.com/docs/en/github-actions))
- **Routine GitHub triggers:** fire on `pull_request.*` and `release.*` events, with filters. They need the Claude GitHub App and have hourly caps. Scheduled routines run at most hourly and have a daily run cap. **V** ([routines](https://code.claude.com/docs/en/routines))
- **Auto-fix PRs:** a cloud session watches CI and review comments and pushes fixes. Needs the GitHub App. **V**

## 4) Private repo access
There are two ways to connect GitHub **V** ([cloud docs](https://code.claude.com/docs/en/claude-code-on-the-web#github-authentication-options)):
- **(a) Claude GitHub App** installed on the specific private repo. The App's permission set is broad: Contents, PRs, Issues, Actions and Workflows are all read/write. GitHub doesn't allow accepting a subset. **V** ([App permissions](https://code.claude.com/docs/en/github-actions#github-app-permissions))
- **(b) `/web-setup`**, which sends your local `gh` token to your Claude account. It then reaches any repo that token can. Note that this token has `admin:org` scope, so this option grants a lot.

In both cases, credentials stay on Anthropic's servers behind a GitHub proxy and never enter the VM. **Recommendation:** use (a), installed on one private repo only.

## 5) Branch/PR model and bringing results back
- Routines push to `claude/`-prefixed branches. Pushes to protected branches, or to branches with someone else's commits, are rejected. **V** ([routines](https://code.claude.com/docs/en/routines#repositories-and-branch-permissions))
- Interactive cloud sessions show a diff against the base branch with inline comments. When the session ends you **create a PR** from claude.ai/code, or teleport to continue locally. **V**
- **U:** that ad-hoc sessions also use `claude/` branch names. That's likely, but the docs only state it for routines.
- To pull results locally, pick one:
  - `git fetch && git checkout <claude/branch>`
  - `gh pr checkout <n>`
  - `claude --teleport <id>`, which needs a clean tree, the same repo (not a fork), the branch already pushed, and the same account. **V**

## 6) Usage, credits and billing
- Cloud sessions **share rate limits with all your Claude and Claude Code usage**. There is **no separate charge for the VM**. **V** ([limitations](https://code.claude.com/docs/en/claude-code-on-the-web#limitations))
- Usage credits (formerly "extra usage") are prepaid dollars billed at **standard API rates**. They kick in after plan limits and generally don't expire. **V** ([usage credits](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans))
- **What "~100 Claude Cloud credits" most likely means:** the **$100 promotional cloud-session credit for Pro** subscribers (Max gets $250). Details:
  - Must be claimed by **Oct 7**. The balance **expires Nov 4**.
  - Applies **only to cloud sessions** and is used **before** plan limits.
  - Claimed at `claude.ai/code/claim-credit/...`.
  - The amount matches exactly: this account is Pro, and the only other plausible candidate, the Pro Agent SDK credit, is $20.
  - **U / partly verified.** I confirmed these terms only in secondary reporting ([BleepingComputer, 2026-09-25](https://www.bleepingcomputer.com/news/artificial-intelligence/anthropic-rolls-out-up-to-250-in-free-claude-code-credits-but-only-for-cloud-sessions/), [gHacks](https://www.ghacks.net/2026/09/26/anthropic-offers-up-to-250-in-free-claude-code-cloud-credits-to-pro-and-max-subscribers/)). I found no official support.claude.com page. **Check the balance at claude.ai/settings/usage.**
- **Unknown:** whether the credit also covers routines or `ultrareview`. Assume it covers only interactive cloud sessions.
- **Important separation:** the take-home app's *own* LLM calls (for example `run_cases.py` hitting the Anthropic API with your key) are **API billing on your key**. They are not covered by subscription usage or the cloud credit, even when run inside a cloud VM. **U** (follows from how keys work)
- **Rough cost, U:** one focused 20–40 min Opus session likely costs single-digit to low-double-digit dollars at API rates. So $100 comfortably covers 3–6 tasks.

## 7) Limitations
All **V** ([cloud-environments](https://code.claude.com/docs/en/cloud-environments)).
- **Network levels:** None, Trusted (default), Full, or Custom.
  - Trusted allows package registries (PyPI, npm), GitHub, cloud SDKs, and `api.anthropic.com`.
  - **Other LLM hosts such as `api.openai.com` are not on the default list**, so a non-Anthropic provider needs Custom or Full.
  - The Anthropic API is reachable even at None.
- **Secrets:**
  - Environment variables are **readable by anyone using the environment**. For a personal environment that's only you.
  - On Pro/Max, "API credentials" are injected by a proxy and never enter the VM, **but never for `api.anthropic.com`**. So an Anthropic key for the app's eval has to go in as a plain environment variable, or evals stay local.
- **Setup scripts:** run before Claude starts. They're cached only if they finish in about 5 min.
- **Timeouts:** Bash commands default to 2 min (max 10, adjustable). SessionStart hooks time out at 600 s.
- **Resources:** about 4 vCPU, 16 GB RAM, 30 GB disk. Python 3 with pip/uv/pytest/ruff is preinstalled.
- **Session length:** no hard cap is documented. Idle sessions expire and the VM is reclaimed. Reopening restores the conversation but not running background work.
- **Other:** PRs require GitHub. On Pro, session sharing can be set **Public**; keep sessions **Private**, since the brief says don't post the solution publicly.

## 8) Can orchestrator v0.5.4 launch or track cloud sessions?
**VERIFIED: no.**
- Providers are local CLIs in tmux panes or headless (`claude -p … --output-format json`). The providers are claude, codex, gemini, grok, shell, and the custom `agy` and `opencode`.
- The 7,191-line source has no references to `--cloud`, `--remote`, `teleport` or `claude.ai/code`. **L**
- `~/.config/agent-team/config.toml` (read-only) has no cloud provider configured. **L**
- `orchestrator worktree`/`land` operate on *local* worktrees only.

**SPECULATIVE (untested, not recommended under time pressure):**
- A `shell` teammate, or a custom `[providers.custom.*]` block, could run `claude --cloud "…"`. I don't know if that returns promptly or blocks on the provisioning checklist.
- Follow-ups via `claude -p "…" --cloud <id> --output-format json` exit cleanly (**V**), so orchestrator could *send* to a session.
- Status or result tracking would still be manual, via claude.ai/code or `gh pr list`.
- `orchestrator land` can't land a cloud branch. You'd `git fetch` the branch into a local branch, and only then might a local review and land flow apply.

## Recommended workflow
1. **Local (orchestrator/lead):** write the task spec, meaning objective, acceptance criteria and file scope, into `tasks/<name>.md`. Log the prompt in PROMPTS.md.
2. **One-time setup, about 10–15 min:**
   - `git init`, then commit the materials and the skeleton.
   - `gh repo create <name> --private` and push. The brief allows a private repo shared with the reviewer.
   - Install the Claude GitHub App **on that repo only**.
   - Claim or confirm the credit at claude.ai/settings/usage.
   - Keep the Default environment (Trusted). Add `ANTHROPIC_API_KEY` as an env var only if the cloud task must run live evals.
3. **Launch:** `claude --cloud "Execute tasks/<name>.md; work only in <paths>; run pytest; commit to a claude/ branch"`. Record the session ID.
4. **Isolated branch → PR:** when the session finishes, click Create PR on claude.ai/code. Keep the session Private.
5. **Local review:** run `gh pr checkout <n>` and read the diff. Run tests and `run_cases.py` locally. Optionally get a review from a *different* provider through orchestrator, so the implementer isn't also the reviewer.
6. **Land:** `gh pr merge --squash`, or merge locally. Log the cloud prompt and outcome in PROMPTS.md.

## Which tasks are worth sending to the cloud, given 2 hours
- **Worth it (independent, well-specified, parallel to your local critical path):**
  - An **eval harness**: a scorer for the must_include/must_not_include regexes, a first-vs-final run diff, and a report. It's deterministic and needs no LLM key.
  - An **expanded adversarial case set**: escalation traps, cross-user data requests, prompt-injection questions. These are drafted as JSONL for you to vet.
  - Possibly a **final independent review pass** of the finished branch.
- **Keep local:**
  - The core pipeline: retrieval, tool-calling, authorization and escalation guardrails, and prompts. This is the graded LLM engineering and needs a tight iteration loop.
  - DECISIONS.md, the README and the iteration note. These are judgment the graders care about.
  - Anything that needs your API key in a loop.
- **Skip entirely:** routines, GitHub Actions `@claude` and auto-fix. They take real setup time and add nothing in a 2-hour window.
- **Net:** cloud earns its setup cost only if you start it in the first ~15 minutes and send 1–2 tasks. Otherwise local orchestrator teammates do the same job with zero setup.

## Recommendation
Treat the cloud as optional, not central. If the user wants to use the ~$100 credit, most likely the Pro cloud-session promo that expires Nov 4:
- Create a **private** GitHub repo and install the Claude App on it only.
- Send exactly **two** bounded tasks via `claude --cloud`: the eval harness and the adversarial cases.
- Review them as PRs locally and land them with `gh`.
- Keep the core LLM pipeline and all writing local.
- Don't try to make orchestrator drive cloud sessions; that isn't supported in v0.5.4.
- Keep cloud sessions Private, and log every cloud prompt in PROMPTS.md.

## Open questions
1. Confirm the credit's identity and balance at claude.ai/settings/usage. I couldn't find an official promo page. Also: has it been claimed yet (deadline Oct 7)?
2. Does the user accept installing the broad-permission Claude GitHub App on a private repo holding the assessment? The alternative is `/web-setup`, which exposes a token with `admin:org` scope.
3. Which LLM provider will the app use? A non-Anthropic provider needs Custom network access for in-cloud evals.
4. Does the credit cover `ultrareview` and routines, or only cloud sessions? Not documented.
5. Does `claude --cloud "<task>"` exit non-interactively, so a script or orchestrator could wrap it? Test once with a trivial task if you ever want to automate it.
