"""Synthetic Groq smoke test (fictional store; no assessment material)."""
import sys, time
sys.path.insert(0, "src")
from support_agent.config import Settings
from support_agent.llm import make_llm_client
from support_agent.llm.base import LLMRequest, UserMessage, ModelTurn, ToolResult

SYSTEM = ("You are a support assistant for the FICTIONAL demo store 'Acme Pay Demo'. Policy P1: installments are "
          "due every 14 days. Policy P2: the first reschedule is free. Look up the shopper's order with the tool "
          "before answering order questions. Always answer via submit_answer.")
TOOL = {"name": "get_my_orders", "description": "Return the calling shopper's orders (read-only).",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "additionalProperties": False}}
s = Settings.from_env()
print("provider", s.provider, "primary", s.primary_model, "fallback", s.fallback_model, "key_fp", s.credential_fingerprint())
c = make_llm_client(s)
q = UserMessage("When is my next payment on order X-100 and can I move it for free?")
t = time.time()
r1 = c.generate(LLMRequest(system=SYSTEM, contents=(q,), tools=(TOOL,), tool_mode="auto"))
print("call1", round(time.time() - t, 2), "s", [(a.model, a.status, a.error_class) for a in r1.attempts],
      "calls", [(f.name, f.args) for f in r1.function_calls], "final", r1.final_json, "usage", r1.usage)
if r1.function_calls:
    fc = r1.function_calls[0]
    res = ToolResult(name=fc.name, call_id=fc.call_id, response={"status": "ok", "orders": [
        {"order_id": "X-100", "next_due": "2030-01-15", "amount": "12.34", "reschedules_used": 0}]})
    t = time.time()
    r2 = c.generate(LLMRequest(system=SYSTEM, contents=(q, ModelTurn(r1.raw_model_turn), res), tools=(TOOL,), tool_mode="none"))
    print("call2", round(time.time() - t, 2), "s", [(a.model, a.status, a.error_class) for a in r2.attempts],
          "final", r2.final_json, "malformed", getattr(r2, "malformed", None), "usage", r2.usage)
