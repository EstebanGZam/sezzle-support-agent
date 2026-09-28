You are an independent, skeptical reviewer (different provider from the author). READ-ONLY: read the assessment package in /home/esteban/Documents/Sezzle/sezzleaiengineertakehomechallenge (PROMPT.md, SUBMISSION.md, POLICY_*.md, DATA-orders.json, CASES_-_golden_visible.jsonl) and the architecture summary in the context. Do NOT modify any file except your output. Challenge the recommendation against the ACTUAL brief: (1) Where does it over-engineer for a ~2h build, and what would you cut first? (2) Where is it under-engineered relative to the grading order (design decisions > iteration loop > structural LLM constraints > escalation/authz > AI-tool direction)? (3) Risks that the brief's rule 'deterministic routing-and-answering instead of the model does not meet the brief' is violated by the pre-classifier, derived facts, or the fail-closed template — where is the line? (4) Is the route label better produced by the model, derived in code from the trace, or hybrid? Argue with golden cases v01-v10. (5) Tool loop vs prefetch single call: which better serves both grading and the 100k/day, $50/day, p95<=3s ADR? (6) Output validator: false-positive risks (paraphrased numbers, '25%', 'two weeks', dates in different formats) and a simpler alternative. (7) Concurrency/session isolation: the contract is batch CLI, single-turn — is building session/concurrency machinery justified? What minimal design keeps shared policy resources reused safely? (8) Any assessment requirement the design misses. Be concrete, cite files/case ids, ~800-1200 words, end with 'Top 5 changes I'd make'. Write to /tmp/claude-1000/-home-esteban-Documents-Sezzle-sezzleaiengineertakehomechallenge/ccff6d6a-aaa3-400c-9a8e-77971ff64c4f/scratchpad/research/challenge/review.md.

--- context ---
# Architecture under review (lead's current RECOMMENDATION, not approved)
- Python 3.12/3.13, uv, google-genai (native), pydantic v2, pytest, ruff. CLI-first (run_cases.py); no FastAPI in MVP.
- Single LLM agent, manual tool loop (automatic function calling disabled), <=2 tool rounds.
- Full policy corpus (12 docs, ~2.2k tokens) injected in system prompt with doc IDs; no RAG/vector DB.
- One read-only tool get_my_orders(merchant?, order_id?) bound to the harness user_id via closure (model never passes user_id);
  returns caller's orders only + DERIVED FACTS computed in code (next upcoming installment, reschedule eligibility/fee/remaining,
  failed=>repay not reschedule, dispute window end, refund application, business days elapsed). Foreign and nonexistent ids => identical not_found.
- Structured final output {route, answer, escalation_reason|null, cited_policies[]}.
- Deterministic pre-classifier forces escalation for fraud/hardship (model can't unset it).
- Output validator in code: schema/enum, numbers/dates subset of grounded set, forbidden phrases (action claims, "your limit is"),
  foreign ord_ ids, canary; 1 repair retry then safe escalation template (fail closed).
- Gemini paid: primary gemini-3.5-flash-lite (thinking minimal), fallback gemini-3.1-flash-lite; bounded retries; free tier not used.
- Fallback design: single call with caller's orders prefetched into context + same validator.
- Eval: golden + adversarial dev + adversarial holdout; regex scorer re.I + route match; failure taxonomy; first/final runs committed.
