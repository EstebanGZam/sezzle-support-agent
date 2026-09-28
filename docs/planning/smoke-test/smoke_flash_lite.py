"""Minimal Gemini Flash-Lite smoke test (synthetic content only; no assessment material).

Checks per model: availability, function calling, structured JSON output combined
with tools on the follow-up turn (thought signatures echoed back), minimal thinking,
latency and token usage. Also probes whether a ~3.3k-token prefix can be explicitly
cached. Uses REST + stdlib only; the API key is read from the environment, never printed.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta"
KEY = os.environ.get("GOOGLE_API_KEY") or os.environ["GEMINI_API_KEY"]
MODELS = sys.argv[1:] or ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
REPS = 3

SYSTEM = (
    "You are a support assistant for FICTIONAL demo store 'Acme Pay Demo'. "
    "Policy P1: installments are due every 14 days. Policy P2: the first reschedule is free. "
    "Use the tool to look up the shopper's order before answering order questions."
)
TOOLS = [{
    "functionDeclarations": [{
        "name": "get_my_orders",
        "description": "Return the calling shopper's orders (read-only).",
        "parameters": {"type": "OBJECT", "properties": {"order_id": {"type": "STRING"}}},
    }]
}]
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "route": {"type": "STRING", "enum": ["policy", "tool", "both", "escalate"]},
        "answer": {"type": "STRING"},
        "cited_policies": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["route", "answer", "cited_policies"],
}
QUESTION = "When is my next payment on order X-100, and can I move it for free?"
TOOL_RESULT = {"orders": [{"order_id": "X-100", "next_due": "2030-01-15", "amount": "12.34",
                           "reschedules_used": 0}]}


def thinking(model):
    return {"thinkingBudget": 0} if model.startswith("gemini-2.5") else {"thinkingLevel": "minimal"}


def post(path, body):
    req = urllib.request.Request(
        f"{BASE}/{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": KEY}, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b"{}").get("error", {})
        return e.code, {"error": {"status": err.get("status"), "message": err.get("message", "")[:200]}}, (time.perf_counter() - t0) * 1000


def usage(resp):
    u = resp.get("usageMetadata", {})
    return {k: u.get(k) for k in ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount",
                                  "cachedContentTokenCount", "totalTokenCount")}


def run_case(model):
    out = {"model": model}
    base = {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "tools": TOOLS,
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}}}
    contents = [{"role": "user", "parts": [{"text": QUESTION}]}]
    s1, r1, ms1 = post(f"models/{model}:generateContent", {
        **base, "contents": contents,
        "generationConfig": {"maxOutputTokens": 512, "thinkingConfig": thinking(model)}})
    out["t1"] = {"http": s1, "ms": round(ms1), "usage": usage(r1), "error": r1.get("error")}
    if s1 != 200:
        return out
    cand = r1["candidates"][0]["content"]
    calls = [p["functionCall"] for p in cand.get("parts", []) if "functionCall" in p]
    out["t1"]["function_call"] = calls[0] if calls else None
    out["t1"]["has_thought_signature"] = any("thoughtSignature" in p for p in cand.get("parts", []))
    if not calls:
        return out
    contents += [cand, {"role": "user", "parts": [{"functionResponse": {
        "name": "get_my_orders", "response": TOOL_RESULT}}]}]
    s2, r2, ms2 = post(f"models/{model}:generateContent", {
        **base, "contents": contents,
        "generationConfig": {"maxOutputTokens": 512, "thinkingConfig": thinking(model),
                             "responseMimeType": "application/json", "responseSchema": SCHEMA}})
    out["t2"] = {"http": s2, "ms": round(ms2), "usage": usage(r2), "error": r2.get("error")}
    if s2 == 200:
        text = "".join(p.get("text", "") for p in r2["candidates"][0]["content"].get("parts", []))
        try:
            obj = json.loads(text)
            out["t2"]["json_valid"] = set(SCHEMA["required"]) <= set(obj)
            out["t2"]["route"] = obj.get("route")
            out["t2"]["grounded_date"] = "2030-01-15" in obj.get("answer", "") or "January 15" in obj.get("answer", "")
            out["t2"]["answer"] = obj.get("answer", "")[:240]
        except json.JSONDecodeError:
            out["t2"]["json_valid"] = False
            out["t2"]["raw"] = text[:200]
    return out


def cache_probe(model):
    # ~3.3k tokens of synthetic filler, mimicking the policy-prefix size.
    filler = " ".join(f"Synthetic policy clause {i}: demo text about installments." for i in range(330))
    s, r, ms = post("cachedContents", {"model": f"models/{model}", "ttl": "60s",
                                        "contents": [{"role": "user", "parts": [{"text": filler}]}]})
    res = {"model": model, "http": s, "ms": round(ms), "error": r.get("error"),
           "cached_tokens": r.get("usageMetadata", {}).get("totalTokenCount")}
    if s == 200 and r.get("name"):
        req = urllib.request.Request(f"{BASE}/{r['name']}", headers={"x-goog-api-key": KEY}, method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=15)
            res["deleted"] = True
        except urllib.error.HTTPError as e:
            res["deleted"] = f"HTTP {e.code}"
    return res


if __name__ == "__main__":
    results = {"runs": [], "cache": []}
    for m in MODELS:
        for _ in range(REPS):
            results["runs"].append(run_case(m))
        results["cache"].append(cache_probe(m))
    print(json.dumps(results, indent=1))
