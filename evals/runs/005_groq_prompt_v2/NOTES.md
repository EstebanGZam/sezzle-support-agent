# Run 005 — prompt v2 (iteration 2) on Groq, plus adapter infra fixes (preserved unedited)

- **Changes vs run 004:**
  1. **Prompt v2** (`PROMPT_VERSION` in `config.json`): decision boundaries, policy consequences and an explicit hand-off, targeting the behaviour classes in `ITERATION.md` §2.
  2. **Groq adapter infra fixes:** `tool_use_failed` recovery; 413-TPM classified as a rate limit; provider error `detail` in traces. These only affect the PROVIDER_ERROR / `bad_request` class, so taxonomy labels keep the two effects apart.
- **Same command overrides as run 004.**

## golden (22:12–22:17)
- Case pass **7/10** (004: 6/10). Regex 7/10. Route **8/10** (004: 9/10).
- Remaining infra issues, now diagnosable from `detail`:
  - v03 `HTTP 400 output_parse_failed`: the model's answer is in `failed_generation` and was not yet recovered (fix follows).
  - v07 hit **`quota_daily` on gpt-oss-120b**: the free-plan 200K TPD per model was exhausted by runs 004/005, and the call failed over to gpt-oss-20b as designed.
- **adversarial_dev:** deferred until the Groq daily token quota recovers; see the next section once run.
