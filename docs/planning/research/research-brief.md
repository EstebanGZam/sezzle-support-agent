# Shared research brief (lead → teammates)

Today: 2026-09-27. You are a read-only RESEARCH teammate in an advisory phase.

## Context
The user is preparing a Sezzle "Applied AI Engineer" take-home: build an LLM-powered
shopper-support assistant over 12 short markdown policy docs + a JSON file of mock
accounts/orders (installment schedules, frozen `today` = 2026-07-01). The assistant
must answer policy questions, look up order data, and escalate what it shouldn't touch.
Key facts from the official brief (PROMPT.md / SUBMISSION.md):
- ~2 hour time budget; honest "unfinished" notes graded positively.
- AI coding tools expected; prompts must be logged in PROMPTS.md.
- "A solution with no working LLM in the pipeline does not meet the brief."
  Deterministic logic AROUND the model is welcome; deterministic answering INSTEAD of it is not.
- Any LLM provider allowed. Data is synthetic.
- Contract: `python3 run_cases.py <cases.jsonl> <answers.jsonl>`; input `{id, question, user_id}`,
  output `{id, route, answer}`, route in policy|tool|both|escalate. Hidden test set graded by regex
  must_include / must_not_include.
- Deliverables: code, DECISIONS.md (exactly 3 ADRs, ≤~10 lines each), first+final eval runs with
  iteration note, PROMPTS.md, half-page README.
- Design constraint for an ADR: 100k questions/day, ~$50/day inference budget, p95 ≤ 3 s.
- Grading order: design decisions > iteration loop > LLM engineering (grounding, what the model is
  STRUCTURALLY prevented from doing) > escalation/authorization judgment > how AI tools were directed.
  Scaffolding quality, provider choice, LOC are NOT graded.
- Submission: zip OR private GitHub/GitLab repo shared with reviewer. "Please don't post the
  challenge or your solution publicly." Public deployment is NOT required by the brief.

## Hard rules for you
- Do NOT install anything, create repos, deploy, launch cloud sessions, or spend credits.
- Do NOT modify files outside your own output directory. Never print or write API keys/tokens.
- Do NOT upload or paste the assessment materials to any external service.
- Prefer OFFICIAL sources; cite URLs inline. Mark each claim VERIFIED (with source) or UNVERIFIED/ASSUMPTION.
  If something changed recently or you can't confirm it, say so. Pricing/limits: quote the page and date.
- Be concise and decision-oriented: the lead needs a recommendation, not an encyclopedia.
  Target 600–1500 words unless told otherwise. End with "Recommendation" and "Open questions".
- Write your final report to the report.md path given in your task, then reply with a 5-line summary.
