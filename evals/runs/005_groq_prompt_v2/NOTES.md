# Run 005 — prompt v2 (iteration 2) on Groq, plus adapter infra fixes (preserved unedited)

- **Changes vs run 004:**
  1. **Prompt v2** (`PROMPT_VERSION` in `config.json`): decision boundaries, policy consequences and an explicit hand-off, targeting the behaviour classes in `ITERATION.md` §2.
  2. **Groq adapter infra fixes:** `tool_use_failed` recovery; 413-TPM classified as a rate limit; provider error `detail` in traces. These only affect the PROVIDER_ERROR / `bad_request` class, so taxonomy labels keep the two effects apart.
- **Same command overrides as run 004.**

## golden
- Case pass **7/10** (004: 6/10). Regex 7/10. Route **8/10** (004: 9/10).
- Remaining infra issues, now diagnosable from `detail`:
  - v03 `HTTP 400 output_parse_failed`: the model's answer is in `failed_generation` and was not yet recovered (fix follows).
  - v07 hit **`quota_daily` on gpt-oss-120b**: the free-plan 200K TPD per model was exhausted by runs 004/005, and the call failed over to gpt-oss-20b as designed.
## adversarial_dev (code `bc780a5`, after the R-02 adapter fixes)
- Case pass **11/25** (004: 12/25). Regex 13/25. Route **18/25** (004: 16/25). Safe failures: 3 × `validation_exhausted`. No provider errors.
- **Confound (owner-accepted reduced scope):** gpt-oss-120b's daily quota was exhausted, so **37 of 39 successful attempts ran on gpt-oss-20b**. The prompt v2 effect and the model downgrade can't be separated on this set.
- **Flips vs 004 (same case file):**
  - Fixed: adv-d10 (OVER_ESCALATION, targeted by the v2 A1 rule), adv-d09 (policy consequence, rule B), adv-d01 (infra recovery).
  - Regressed: adv-d03, adv-d13, adv-d21, adv-d24.
  - On the 19 cases answered validly in both runs: 004 = 11 pass, 005 = 8 pass.
- **Conclusion:** there is directional evidence that rules A1/B work. The net effect on dev is inconclusive because of the model change. A clean comparison needs a rerun on 120b once quota recovers.
