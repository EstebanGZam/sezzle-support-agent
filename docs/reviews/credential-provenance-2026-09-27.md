# Credential Provenance Investigation — Gemini smoke tests (2026-09-27)

Requested by the owner (P-005 §1, §10). Uses existing evidence and non-secret metadata only. **No credential value is shown anywhere.** Fingerprints are the first 12 hex characters of SHA-256 over the key string, which is not reversible. No new API calls were made for this investigation.

## 1. Which credential the smoke tests used
- `docs/planning/smoke-test/smoke_flash_lite.py` line 17 reads `GOOGLE_API_KEY` if set, otherwise `GEMINI_API_KEY`.
- In the session environment, `GOOGLE_API_KEY` is **unset** and `GEMINI_API_KEY` is **set**. Therefore every Gemini call in this workflow used `GEMINI_API_KEY`:
  - A-003's single `models.list`;
  - the lead's `models.list` of Flash-Lite models;
  - the S-001 smoke test.
- Key metadata: length 39; standard Google API key format (`AIza…` prefix); fingerprint **`53408af16a25`**.
- The owner never provided a key in the conversation. The key reached the agents by **environment inheritance**, not by any explicit hand-off.

## 2. Where the variable comes from
Process ancestry (variable names only):

| Process | Has `GEMINI_API_KEY` |
|---|---|
| tool shell (bash) | yes |
| `claude` (lead session) | yes |
| `tmux: server` (started 2026-09-27 18:29:26) | yes |
| parent `systemd --user` / `systemd` | environ not readable |

Other sources checked:
- `tmux show-environment -g` lists `GEMINI_API_KEY`. It is in the **tmux global environment**, so every Orchestrator teammate pane inherits it.
- Not defined in `~/.bashrc`, `~/.profile`, `~/.bash_profile`, `~/.zshrc`, `/etc/environment`, `/etc/profile(.d)`, or `~/.config/environment.d`. It is not in the systemd user environment.
- **Most likely origin:** exported in the terminal that launched the tmux/orchestrator session, or set via `tmux set-environment`. The exact origin can't be determined from files. [ASSUMPTION]
- It is **not** the key stored in another local project that references the same variable name (`…/aiops-bot/.env`, fingerprint `ba235477e643` ≠ `53408af16a25`).
- **Owner check (local, never paste the key):** `printf %s "$YOUR_KEY" | sha256sum | cut -c1-12`. A match with `53408af16a25` means your validated key is the same credential the agents used.

## 3. What the evidence does and does not show

| Observation (unchanged, from `docs/planning/smoke-test/results.json`) | Establishes | Does not establish |
|---|---|---|
| 15 × `generateContent` HTTP 200 on `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-2.5-flash-lite` (turn 1), and 3.x turn 2 | **Inference is available** with this key for these models | Billing status. Free-tier projects can also call these models |
| 3 × `generateContent` HTTP 400 on `gemini-2.5-flash-lite` turn 2: "Function calling with a response mime type: 'application/json' is unsupported" | Capability incompatibility of 2.5 Flash-Lite. Not an auth/billing issue | — |
| 3 × `cachedContents.create` HTTP 429 `RESOURCE_EXHAUSTED`: "`TotalCachedContentStorageTokensPerModelFreeTier limit exceeded … limit=0, requested=4181`" | At that time, the **cache-storage quota** evaluated for this key's project was the free-tier bucket, with limit 0 | That paid inference is unavailable. Inference and cache storage are different quota metrics |
| Owner's independent call (P-005): `gemini-3.8-flash` HTTP 200, `serviceTier: standard`, `finishReason: MAX_TOKENS` | Authentication and invocation work for the owner's credential | Billing: `serviceTier` describes the processing tier, not the account's billing status (owner's own statement) |

**Conclusion:**
- Inference availability is confirmed.
- The billing and data-handling tier of the project behind fingerprint `53408af16a25` is **unverified**.
- The cache-quota error is a *signal* consistent with an unbilled project, not proof of one.
- The owner's validated credential may or may not be the same key (see the check in §2).
- Caching is **not** a functional prerequisite: the architecture works without it. Caching affects only the cost analysis in ADR-3.

## 4. Consequences for the specs (applied)
- **A-10 revised:** original observation preserved; interpretation corrected (`specs/assumptions.md`).
- **Explicit key source (AR-09, proposed):** the application reads the key **only** from `GOOGLE_API_KEY` (normally via `.env`) and passes it explicitly to the SDK. It never falls back to an inherited `GEMINI_API_KEY`. The SDK's own env lookup would otherwise pick up the tmux-inherited key silently.
- **Credential provenance recorded per run:** each run's `config.json` records `credential_env_var` and `credential_fingerprint` (12-hex SHA-256 prefix), never the value. Evaluation evidence then shows which credential produced it.
- **Explicit caching** is optional. The first real run measures `cachedContentTokenCount` (implicit caching). ADR-3 reports what was actually observed.
