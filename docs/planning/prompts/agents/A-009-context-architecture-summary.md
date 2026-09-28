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
