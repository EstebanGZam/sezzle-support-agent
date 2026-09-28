# Requirements Analysis — Sezzle Applied AI Engineer take-home

Analyst: Requirements Analyst (read-only). Sources read: every file in
`/home/esteban/Documents/Sezzle/sezzleaiengineertakehomechallenge/` (PROMPT.md, SUBMISSION.md,
12 × `POLICY_-*.md`, `CASES_-_golden_visible.jsonl`, `DATA-orders.json`). All claims below are
VERIFIED against those files (file + line cited) unless marked INFERENCE / ASSUMPTION / OPEN.
Line numbers = `cat -n` of the file. "v01…v10" = golden case IDs (CASES line = case number).
Frozen date: `today = 2026-07-01` (Wednesday) — DATA-orders.json line 3.

---

## 1. Requirements traceability matrix

Type key: **EXP** = explicit requirement · **DOC** = documented restriction (policy text) ·
**INF** = technical inference · **REC** = recommendation · **OQ** = open question.
All rows: Status = **Not started**.

### 1a. Functional / behavioral

| ID | Description | Source | Type | Prio | Acceptance criteria | Verification | Status |
|---|---|---|---|---|---|---|---|
| F-01 | LLM-powered assistant that answers what it can, looks up what it must, escalates what it shouldn't touch | PROMPT.md L13-16 | EXP | Must | Every case produces an LLM-generated answer + route | Run golden; inspect trace shows LLM call per case | Not started |
| F-02 | A working LLM must be in the pipeline; deterministic routing-and-answering *instead of* the model fails the brief | PROMPT.md L18-25; SUBMISSION.md L12-14 | EXP | Must | Disable the LLM ⇒ system cannot answer (no hard-coded answer table) | Code review; kill-switch test | Not started |
| F-03 | Deterministic logic *around* the model (pre-filters, authz, output validation) is welcome | PROMPT.md L23-25 | EXP | Should | Guardrails exist in code, not only in prompt text | Code review; ADR cites them | Not started |
| F-04 | Grounding: no invented facts; policy claims come from the 12 docs, order facts from the data | PROMPT.md L20-21; grading #3 L96-97 | EXP | Must | 0 numbers/dates in answers absent from policy text or the user's records | Output validator (numbers ⊂ context) + manual read | Not started |
| F-05 | Specific-order next payment/amount answered from the order record, not generic policy | POLICY_-_01 L15-16; v01 | DOC | Must | v01 returns 2026-07-11 and 118.36 (not 25% of total = 118.375) | Golden v01 | Not started |
| F-06 | Use the file's `today` as current date (never the system clock — real date is 2026-09-27) | PROMPT.md L35-36; DATA L3 | EXP | Must | "Next payment" / window math uses 2026-07-01 | Unit test with clock mocked to other date | Not started |
| F-07 | Authorization: only the asking `user_id`'s orders are visible; other users' / nonexistent order IDs neither confirmed nor leaked | PROMPT.md L85-86 (Eng II) | EXP | Must | "Tell me about ord_3006" as u001 ⇒ no merchant/amount/date of ord_3006 in answer | Adversarial cases; tool scoped by user_id in code (model never passes user_id) | Not started |
| F-08 | No ad-hoc fee waivers/discounts; only the automatic once/12-month rule may be *described* | POLICY_-03 L10-12; POLICY_-10 L10-12; PROMPT L86 | DOC | Must | Waiver demand ⇒ refuse + escalate fee dispute; never "I waived/will waive" | Adversarial cases; must_not regex | Not started |
| F-09 | Guardrails survive prompt injection ("ignore your rules") | PROMPT.md L85-87 | EXP | Must | Injection cases keep policy behavior and do not leak system prompt/other users | Adversarial suite | Not started |
| F-10 | Escalation triggers: dispute filing (05), hardship (09), fraud/ATO (11), specific decline reason / exact limit / override (12), fee disputes beyond policy (03), already-reported credit data or corrections (07), approved refund not seen after 10 business days (04) | Policies cited | DOC | Must | Each trigger ⇒ route `escalate` + handoff phrase ("human agent"/"escalat") | Golden v05-v07,v09 + 1 synthetic case per trigger | Not started |
| F-11 | Escalate answers still explain the *allowed* general policy (e.g., dispute 90d/15d/pause; general limit factors; password/2FA) | v06 must_include; POLICY_-05 L13-14; POLICY_-12 L10-12; POLICY_-11 L7 | DOC | Must | v06 includes disput·90·15·paus; v09 includes password/2FA | Golden v06, v09 | Not started |
| F-12 | Fraud: escalate immediately, advise password + 2FA, don't read back payment/address/order contents, no fraud determination | POLICY_-11 L6-12; v09 | DOC | Must | v09 contains no `ord_`, amounts, merchant names | Golden v09 + must_not `ord_\|\$\d` (own check) | Not started |
| F-13 | Hardship: escalate empathetically; no negotiation, no promised pauses/waivers, no qualification statement, no detail collection | POLICY_-09 L7-10; v07 | DOC | Must | v07 lacks "I've paused", "waived" (even in negation) | Golden v07 | Not started |
| F-14 | Sezzle Up answers must mention late/failed payments are also reported | POLICY_-07 L6-7 | DOC | Must | Any Sezzle Up answer matches `late\|fail` + `report` | Synthetic case | Not started |
| F-15 | Policy-route answers must not include order data | v02 must_not `ord_`; v02 "why" | EXP (via golden) | Must | Generic questions contain no `ord_`, no user amounts | Golden v02 | Not started |
| F-16 | Reschedule evaluation vs order state: 1st free ≤2 weeks; 2nd/3rd $5; max 3; ≥24h before due; failed installments not reschedulable (repay instead); amount never changes; later installments don't shift | POLICY_-02 L5-14; POLICY_-10 L6 | DOC | Must | v03 says free + 2 weeks; v04 says repay + cannot reschedule; rs=2 order ⇒ "$5, last one allowed" | Golden v03, v04 + synthetic (ord_3020, ord_3002) | Not started |
| F-17 | Refund logic: merchant approves first; applied to unpaid installments first; last installment shrinks first; excess back in 3–10 business days; escalate if >10 business days | POLICY_-04 L3-15; v10 | DOC | Must | v10 mentions remaining/unpaid rule, 3, 10 business days, "still inside window" | Golden v10 | Not started |
| F-18 | Assistant never claims to have performed a write action (reschedule, pause, file dispute, waive, reactivate) — no write API exists in the kit | v07 must_not "I've paused"; PROMPT L32 "data only" | INF | Must | No first-person past-tense action claims | must_not regex over all answers | Not started |
| F-19 | Order disambiguation by merchant name (users refer to "my Nordic Kicks order"); several users have 2 orders at same merchant | DATA (u001 Peak Threads ×2, u003 Bloom & Vine ×2, u006 Circuit City ×2, u007 Bloom & Vine ×2, u008 Atlas ×2) | INF | Should | Ambiguous ⇒ use question cues (e.g., "missed" ⇒ failed one) or cover both / ask | Synthetic cases | Not started |
| F-20 | Unknown `user_id` or user with no matching order handled without hallucination | INF (hidden set "same format", any user_id) | INF | Should | u999 ⇒ graceful "can't find account" / escalate, no invented orders | Synthetic case | Not started |
| F-21 | Never disclose exact limit or formula; no invented limit numbers | POLICY_-12 L5-7; v05 "critical fail" | DOC | Must | No `$` amount presented as limit | Golden v05 | Not started |
| F-22 | Reactivation is self-serve (automatic after paying overdue + fees; $10 if >30 days deactivated) — not an escalation | POLICY_-06 L3-11 | DOC | Should | Reactivation question ⇒ policy/both, not escalate | Synthetic | Not started |
| F-23 | Same-day reschedule requests "cannot be processed by support or the app" ⇒ answer "no", not escalate | POLICY_-02 L8-9 | DOC | Should | Due-today/tomorrow-<24h case ⇒ refusal with reason | Synthetic | Not started |
| F-24 | Regex grading hazard: forbidden substrings fail even in negation ("your limit is", "waived", "I've paused") | v05, v07 must_not | INF | Must | Output validator scans for known forbidden phrasings; prompt style avoids them | Validator unit test | Not started |
| F-25 | Scope: single-turn Q→A (no conversation state in contract) | PROMPT L46-48 | INF | Should | run_cases processes each line independently | Code review | Not started |

### 1b. Contract (run_cases.py I/O)

| ID | Description | Source | Type | Prio | Acceptance criteria | Verification | Status |
|---|---|---|---|---|---|---|---|
| C-01 | CLI: `python3 run_cases.py <cases.jsonl> <answers.jsonl>` | PROMPT L46-52 | EXP | Must | Exit 0, output file written at given path | Run on golden file | Not started |
| C-02 | Input JSONL `{id, question, user_id}`; must tolerate extra keys (`expected_route`, `must_include`, `must_not_include`, `why`) since hidden set is "same format" as golden | PROMPT L38-42, L47; CASES | EXP+INF | Must | Golden file (with extra keys) runs unchanged | Run golden | Not started |
| C-03 | Output JSONL `{id, route, answer}`, one line per input, id preserved | PROMPT L47-48 | EXP | Must | `len(out)==len(in)`, ids equal set | Contract test script | Not started |
| C-04 | `route` ∈ {`policy`,`tool`,`both`,`escalate`} (exact lowercase) | PROMPT L39; CASES | EXP | Must | Enum validated in code before write (not trusted from LLM raw) | Contract test | Not started |
| C-05 | One case failing (LLM timeout/parse error) must not abort the run; emit safe fallback (e.g., `escalate` + handoff text) | INF | REC | Should | Fault-injected case still yields a line | Unit test | Not started |
| C-06 | Reviewer must be able to run it: deps pinned, provider/API-key env vars documented, works from repo root | PROMPT L27-29, L79 | INF | Must | Fresh venv + README steps reproduce golden run | Clean-checkout dry run | Not started |
| C-07 | Hidden set graded by regex must_include / must_not_include; "build for the problem, not the ten cases" | PROMPT L40-42 | EXP | Must | Pass rate on own held-out synthetic set ≈ golden pass rate | Eval harness with extra cases | Not started |
| C-08 | Regex case-sensitivity & route scoring method unspecified (golden uses lowercase `july 11`, implies case-insensitive) | CASES v01 | OQ | Should | Own scorer runs case-insensitive; answers use ISO dates *and* natural wording to be safe | Scorer config | Not started |
| C-09 | Data file paths: code should locate `DATA-orders.json` / policy files robustly (flat names differ from PROMPT's `data/…` paths) | See §2 | REC | Should | Configurable path; README states layout | Run from repo root | Not started |

### 1c. Non-functional (cost/latency ADR)

| ID | Description | Source | Type | Prio | Acceptance criteria | Verification | Status |
|---|---|---|---|---|---|---|---|
| N-01 | ≥1 ADR states what you'd trade to meet 100k q/day, ~$50/day, p95 ≤ 3 s | PROMPT L57-62 | EXP | Must | ADR names concrete trade (model tier, call count, caching, fallbacks) | Read DECISIONS.md | Not started |
| N-02 | Budget math: $50/100k = **$0.0005 per question** (all LLM calls combined); ~1.2 q/s average, peaks higher | INF from L59 | INF | Must | ADR shows per-question token/cost estimate vs $0.0005 | Arithmetic in ADR | Not started |
| N-03 | p95 ≤ 3 s ⇒ bounded LLM round-trips (≈1–2 calls), small/fast model for routing, no unbounded agent loop | INF | INF | Should | Measured latency per case logged in eval; p95 reported | Eval log | Not started |
| N-04 | Senior bar: cost/latency ADR "reads like it's been lived" (measured numbers, failure modes, what degrades first) | PROMPT L88-89 | EXP | Should | ADR cites measured tokens/latency from own runs | Read | Not started |
| N-05 | Eval should cost "cents" — keep token use small | PROMPT L28-29 | EXP | Could | Total eval cost logged | Eval log | Not started |

### 1d. Deliverables

| ID | Description | Source | Type | Prio | Acceptance criteria | Verification | Status |
|---|---|---|---|---|---|---|---|
| D-01 | Code + run_cases.py | PROMPT L66 | EXP | Must | See C-01…C-06 | Run | Not started |
| D-02 | `DECISIONS.md`: **exactly 3** records, each ≤ ~10 lines: decision · options considered · why · evidence that would change mind | PROMPT L67-71 | EXP | Must | 3 headings; each has 4 labeled parts; ≤ ~10 lines | `grep -c` + read | Not started |
| D-03 | Iteration evidence: **first** full visible run + **final** run (transcripts or answers) + note: what first run got wrong, what changed, why | PROMPT L72-76 | EXP | Must | Two preserved answer files (raw, unedited) + delta table | Files exist; scores differ with explanation | Not started |
| D-04 | `PROMPTS.md`: build prompts (incl. scaffolding) **and** in-system prompts | PROMPT L9, L77-78; SUBMISSION L8-10 | EXP | Must | Both sections present | Read | Not started |
| D-05 | `README.md` ≈ half page: how to run + what's honestly unfinished | PROMPT L79 | EXP | Must | ≤ ~30 lines; has Run + Unfinished sections | Read | Not started |
| D-06 | Senior bar: iteration note shows failure **taxonomy** (categories of failure, not just one fix) | PROMPT L88-89 | EXP | Should | Note groups failures by class (routing, grounding, regex/phrasing, authz…) | Read | Not started |
| D-07 | Decision records + iteration evidence matter more than extra features | SUBMISSION L20-22 | EXP | Must | Time spent prioritizes D-02/D-03 | Self-check | Not started |

### 1e. Grading weights & level expectations

| ID | Description | Source | Type | Prio | Acceptance criteria | Verification | Status |
|---|---|---|---|---|---|---|---|
| G-01 | Weight order: (1) design decisions/options & "what would change my mind" > (2) iteration loop > (3) LLM engineering (grounding, tool/prompt design, *structural* prevention vs instruction) > (4) escalation & authz judgment > (5) AI-tool direction | PROMPT L91-99 | EXP | Must | Each area has a visible artifact | Checklist | Not started |
| G-02 | Not graded: scaffolding quality, provider choice, LOC | PROMPT L101 | EXP | — | Don't spend time polishing scaffolding | — | Not started |
| G-03 | Reviewer rubric: design decisions, iteration, technical depth, evaluation honesty, communication | SUBMISSION L26-27 | EXP | Must | README/notes are honest (report failures) | Read | Not started |
| G-04 | Follow-up interview walks through **your** decision records; be ready to argue rejected alternatives | SUBMISSION L28-29 | EXP | Must | Each ADR lists ≥2 real alternatives | Read | Not started |
| L-01 | Eng I: working LLM pipeline, grounded answers on common cases, one real iteration | PROMPT L83-84 | EXP | Must | Golden mostly passing; 1 documented iteration | Eval | Not started |
| L-02 | Eng II: + guardrails vs hostile input (foreign/nonexistent order IDs, fee-waiver demands, ignore-your-rules) + ADRs weighing real alternatives | PROMPT L85-87 | EXP | Must (target) | Adversarial suite passes | Eval | Not started |
| L-03 | Senior: + lived cost/latency ADR + failure taxonomy | PROMPT L88-89 | EXP | Should (stretch) | N-04, D-06 met | Read | Not started |

### 1f. Submission, confidentiality, time

| ID | Description | Source | Type | Prio | Acceptance criteria | Verification | Status |
|---|---|---|---|---|---|---|---|
| S-01 | Submit zip **or** private GitHub/GitLab repo shared with named reviewer, by replying to the original message | SUBMISSION L18-21 | EXP | Must | Repo private / zip attached | Check visibility | Not started |
| S-02 | Do not post challenge or solution publicly (implies: no public repo, no public deployment, no public gists; secrets never committed) | SUBMISSION L24 | DOC | Must | Repo private; no API keys in history | `git log -p` secret scan | Not started |
| S-03 | Questions → hiring-manager email; good clarifying questions are a positive signal | SUBMISSION L15-16 | EXP | Should | 3–6 questions sent early (see §2.3) | Sent mail | Not started |
| S-04 | If no model access, email HM before starting | PROMPT L30; SUBMISSION L12-14 | EXP | Must | N/A if a provider works | — | Not started |
| S-05 | Data is synthetic (no real PII) | SUBMISSION L11 | EXP | — | — | — | Not started |
| S-06 | AI tools expected; how you direct them is evaluated, never held against you | PROMPT L6-9; SUBMISSION L8-10 | EXP | Must | PROMPTS.md shows directed, critical use | Read | Not started |
| T-01 | Time budget ~2 h; stop at budget and write what you'd do next | PROMPT L3-4; SUBMISSION L3-5 | EXP | Must | README "Next steps" + time log | Read | Not started |
| T-02 | Honest "unfinished" note graded positively | PROMPT L4; SUBMISSION L4-5 | EXP | Must | Unfinished section exists and is specific | Read | Not started |
| T-03 | Whether prep/reading/setup/provider-signup time counts toward 2 h is unspecified | — | OQ | Should | State own accounting in README (e.g., "~2h build, excl. reading") | Read | Not started |

---

## 2. Discrepancies & gaps in the package

### 2.1 Package vs. PROMPT.md (VERIFIED by `ls`)
1. **`llm.py` missing** — PROMPT L27-29 says "`llm.py` in this kit is an optional minimal client"; not in the folder. Impact: low (optional), but worth mentioning to HM and in README.
2. **`data/mock_orders_api.py` missing** — PROMPT L36-37. Impact: low; integrate directly with the JSON (an in-process tool function is equivalent).
3. **Paths/names differ**: PROMPT says `data/policies/`, `data/orders.json`, `cases/golden_visible.jsonl`; package is flat: `POLICY_-_01-payment-schedules.md`, `POLICY_-02-…`…`POLICY_-12-…` (note inconsistent `_-_01` vs `_-02` prefix), `DATA-orders.json`, `CASES_-_golden_visible.jsonl`. Looks like an export/flattening artifact. **Risk:** if the grader's harness assumes `data/orders.json`, our code must find it. Recommendation: restructure into the documented `data/`/`cases/` layout inside the repo (copy, don't rename originals) and make paths configurable.
4. **Golden has an undocumented `why` field** (all 10 lines) — harmless; confirms C-02 (ignore extra keys).
5. **12 policy docs present** ✓ (matches L34).

### 2.2 Specification gaps / ambiguities
- **Time accounting** (T-03): does reading/setup count toward 2 h? Is going over penalized or just noted?
- **Route scoring** unspecified: exact-match accuracy? weighted vs regex checks? How are "both" vs "tool" near-misses treated?
- **Regex flags** unspecified (case-insensitive? multiline?). Golden `july 11` lowercase ⇒ likely `re.I`.
- **Mixed intents**: v06 is route `escalate` yet *must* explain dispute policy (90/15 days, pause) — i.e. escalate ≠ "refuse and hand off"; escalate *dominates* route while content still includes policy (and possibly order facts). v05 likewise escalate + general limit factors allowed. v09 escalate + password/2FA advice.
- **v10 `must_include` "remaining|unpaid…"** although ord_3014 is fully paid: the grader expects the policy rule to be *stated* (refund applies to unpaid first → none left → full $185.19 goes back to payment method). Also regex `"3"` is trivially satisfied by any "3".
- **Authorization route label**: when a user asks about someone else's / nonexistent order, which route is "correct" (tool? escalate?) — not specified.
- **Reviewer run environment**: will reviewers run with their own API key? which env var/provider? network access? If they can't run it, committed answers files are the only evidence.
- **Hidden set data**: same `DATA-orders.json` or a different file? Assume same file, same `today`.
- **"Approved on June 28"** (v10) vs data `issued_date` 2026-06-28: policy's 10-business-day clock is from *merchant approval* (POLICY_-04 L13-14) but data only has *refund issued* date — treat as equal; state assumption.
- **Holidays in business-day math**: 2026-07-04 is a Saturday ⇒ US federal holiday observed **Fri 2026-07-03**. Policy doesn't say whether holidays count. Changes 10-bd deadlines by one day (see §3).
- **Reschedule "up to 2 weeks"** stated only for the *first (free)* reschedule; max push for paid reschedules unspecified. Also whether a push may pass the next installment's date is unspecified.
- **24-hour rule vs "morning batch local time"**: exact cutoff for an installment due tomorrow is ambiguous (time of day of `today` unknown).
- **Fees not represented in data**: no fee ledger, failure-notice timestamps, deactivation dates, limits, payment methods, dispute-open dates, merchant-contact dates, Sezzle Up enrollment ⇒ many policy clauses (waiver eligibility, $10 reactivation, "3+ deactivations") **cannot be evaluated** from data; answers must be conditional, never asserted.

### 2.3 Draft clarifying questions for the hiring manager (send early)
1. **Package layout:** PROMPT.md references `llm.py`, `data/mock_orders_api.py` and `data/…`/`cases/…` paths, but my package is flat (`DATA-orders.json`, `POLICY_-*.md`, `CASES_-_golden_visible.jsonl`) with no `llm.py`/mock API. Is that intentional, and will the hidden set run against this same `DATA-orders.json` (same `today` = 2026-07-01)?
2. **Scoring:** Is `route` scored as exact match separately from the regex checks, and are `must_include`/`must_not_include` applied case-insensitively? For mixed cases (e.g., "never shipped" → escalate *and* explain dispute windows), is `escalate` always the expected label when any human-only action is involved?
3. **Running the hidden set:** Will you run `run_cases.py` with your own API key (which provider/env var should I support), or should I also ship pre-computed answers? Any constraints on network access or runtime?
4. **Data semantics:** Several installments are `failed` with `due_date` *after* `today` (e.g., ord_3016 due 2026-07-10), and users' `reschedules_used` is `{}` while orders carry counts 0–2. Should I treat order-level `reschedules_used` as authoritative and treat these failures as "first attempt failed, retry pending"?
5. **Authorization cases:** When a shopper asks about an order ID that isn't theirs or doesn't exist, what route label do you expect (`tool` with a refusal, or `escalate`)?
6. **Time budget:** Does reading the materials / provider setup count toward the ~2 hours?

---

## 3. Data analysis of `DATA-orders.json` (all VERIFIED by script; today = Wed 2026-07-01)

**Global:** 8 users (u001–u008), 23 orders (ord_3001–ord_3023), all `plan: pay_in_4`. All users `account_status: "active"` and user-level `reschedules_used: {}`. Order statuses: `active`, `completed`, `payment_failed`, `dispute_open`. Installment statuses: `paid`, `upcoming`, `failed`, `paused`. Installment amounts are unequal by cents (last one absorbs rounding — e.g. ord_3006: 118.38×3 + **118.36**) ⇒ model must read the record, not compute 25%. Duplicate first/last names (Jordan ×2, Reyes ×3, Marsh ×2, Sam ×2) ⇒ never authorize by name. Several due dates fall on weekends (e.g. 7/11 Sat, 7/05 Sun) — policy says auto-charge on due date; no weekend rule.

### 3.1 Edge cases a hidden set could probe

| Theme | Record(s) | Fact | What a correct answer must handle |
|---|---|---|---|
| **Failed installment with due date AFTER today (oddity)** | ord_3002 (u001) inst 2 $56.41 due **07-09**; ord_3016 (u006) inst 2 $45.66 due **07-10**; ord_3017 (u006) inst 2 $16.37 due **07-02** | A charge can't normally fail before its due date; account_status still `active` | Don't reason from dates: status `failed` ⇒ "must be repaid, can't be rescheduled" (v04). Fee/deactivation: state conditionally ("if the automatic retry after 48 h fails, a $10 fee applies and the account is deactivated for new purchases") — do **not** assert a fee was charged or waiver eligibility (no failure-notice timestamp exists). ASSUMPTION: first attempt failed, retry pending (consistent with `active`). |
| Failed order + rs=2 | ord_3002 | Failed inst 2; inst 3 upcoming 07-23; reschedules_used 2 | "Can I reschedule?" ⇒ inst 2: no, repay; inst 3: technically eligible as 3rd (final) reschedule at $5 — policy silent on rescheduling on an order with a failed payment (OQ). |
| **Paused installments under dispute** | ord_3001 (u001, Luma Home) status `dispute_open`, inst 3 (07-09) & 4 (07-23) `paused`, rs=2 | Paused ≠ upcoming | "When's my next payment?" ⇒ none will be charged while dispute is under investigation (POLICY_-05 L9-10); don't present 07-09 as a charge date; don't comment on dispute outcome; dispute updates are human-only ⇒ escalate if asked to update/close. Reschedule of paused installment: not "upcoming" ⇒ not applicable. |
| **Refund processing on fully-paid order** | ord_3003 (u001) $63.74 issued Tue 06-30; ord_3004 (u001) $67.37 Mon 06-29; ord_3014 (u005, v10) $185.19 **Sun** 06-28; ord_3023 (u008) $96.31 **Sat** 06-20 | Unpaid balance = 0 | Policy ⇒ nothing to apply to installments, full refund to payment method in 3–10 business days. Still within window in all cases as of 07-01 — **no escalation yet**. |
| **Refund processing on partially-paid order** | ord_3009 (u003, Circuit City Lights) $102.71 issued Thu 06-25; unpaid $308.14 (inst 2–4 upcoming 07-05/07-19/08-02) | Refund < unpaid balance | Policy ⇒ applied to unpaid installments, last installment shrinks first ⇒ inst 4 ($102.72) reduced to ≈$0.01; **nothing** returned to card. But data still shows inst 4 at full amount (status `processing`) — must NOT state the schedule has already changed; say "once processed". "Next payment" for ord_3009 remains $102.71 on 07-05 (Sunday). |
| Business-day windows (no holidays / with Fri 07-03 observed holiday) | 06-20 → 3bd 06-24, 10bd **07-03** / 07-06 · 06-25 → 07-09 / 07-10 · 06-28 → 07-01 / 07-10 → **07-10 / 07-13** · 06-29 → 07-13 / 07-14 · 06-30 → 07-14 / 07-15 | Elapsed as of 07-01: 8, 4, 3, 2, 1 bd respectively | ord_3023 is closest to the 10-bd escalation threshold (8 elapsed) — a hidden "where's my refund" for u008 still ⇒ within window (both/tool), not escalate. Recommend computing dates in a deterministic tool (weekday-only), not by the LLM; state holiday assumption. Also weekend issue dates (06-20 Sat, 06-28 Sun) start counting next business day. |
| **Reschedules 0 / 1 / 2** | rs=0: most active orders (e.g. ord_3006, 3007, 3008, 3011, 3012, 3016, 3021, 3022); rs=1: ord_3004 (fully paid); rs=2: ord_3001, 3002, 3014, 3017, 3018, **3020**; no order at 3 | Next reschedule: rs0 ⇒ free ≤2 wks; rs1 ⇒ $5; rs2 ⇒ $5 and it is the **last allowed** (max 3); rs3 would be ⇒ refuse | Key probes: ord_3018 (u006, inst 3 07-10, rs2) and ord_3020 (u007, inst 2 07-04, rs2) ⇒ "$5, final reschedule". Max-reached (rs=3) state does not exist in data; handle generically. |
| 24-hour rule | Upcoming nearest: ord_3007 & ord_3021 07-03 (2 days), ord_3020 07-04, ord_3009/3022 07-05; failed ord_3017 07-02 | No *upcoming* installment due 07-01 or 07-02 | All upcoming installments pass the ≥24 h test; a "reschedule my payment due today/tomorrow" probe on the data is only possible via ord_3017 (failed ⇒ repay rule dominates). |
| **Other users' orders** | e.g. u001 asking about ord_3006 (u002) or "my Nordic Kicks order" (u001 has none) | Merchant names overlap across users (Nordic Kicks: u002, u004; Circuit City: u001, u003, u005, u006; Bloom & Vine: u002, u003, u007; Luma Home: u001, u004, u005, u006) | Tool must filter by the request's `user_id` in code; "no such order on your account" without confirming existence elsewhere. Nonexistent IDs (ord_9999) ⇒ same response (no oracle). |
| Same-merchant ambiguity | u001 Peak Threads (3002 failed, 3004 refund); u003 Bloom & Vine (3007, 3008) — **v06**; u006 Circuit City (3016 failed, 3018 active rs2) — **v04**; u007 Bloom & Vine (3020 rs2, 3021 rs0) — **v07**; u008 Atlas (3022, 3023 refund) | — | Use cue words ("missed" ⇒ failed), else answer for both or ask. v07 "next week's payment" = 07-03 $34.23 (ord_3021) and 07-04 $37.27 (ord_3020) — but hardship ⇒ escalate, no promises. |
| Dispute 90-day eligibility | All 23 orders are within 90 days of today; soonest deadlines: ord_3015 (u006) **07-24**, ord_3013 (u005) **07-29**, ord_3003 08-04 | — | Could be asked "can I still dispute?" ⇒ yes + deadline, filing is human ⇒ escalate. Also 15-day merchant-contact precondition cannot be verified from data (no contact date) ⇒ state as requirement. |
| **User-level `reschedules_used: {}` vs order-level counts** | all users `{}`; orders 0/1/2 | Policy is per order ("on an order", "per order" — POLICY_-02 L5-7) | **Recommend order-level as authoritative** (matches policy granularity and golden v03 "reschedules_used=0" refers to the order). Treat user-level `{}` as unused/vestigial — not "zero" — and document in DECISIONS/README. Ask HM (Q4). |
| Account status vs failed orders | u001 & u006 have `payment_failed` orders yet `active` | POLICY_-03 L6-7: deactivation only after retry fails | Consistent with "retry pending"; don't tell them they're deactivated. Reactivation fee ($10, >30 days) not derivable. |
| Orders `active` though fully paid | ord_3003, 3004, 3014, 3023 (all with processing refunds) | vs `completed` for 3005, 3010, 3013, 3015, 3019 | "Active" likely = refund open; don't say "you still owe". |
| Completed orders with rs=2 | ord_3013, ord_3015 | nothing upcoming | "Reschedule" ⇒ nothing to move. |

---

## 4. Route-decision rubric (derived from policy text + golden labels)

Apply in order; first match wins for the **label**, but content rules are cumulative.

1. **`escalate`** — the request needs a human-only action or judgment:
   - item not received / wrong / not as described ⇒ dispute filing (POLICY_-05 L13-14; v06)
   - financial hardship, job loss, medical, disaster (POLICY_-09; v07)
   - unauthorized order, stolen card, account takeover (POLICY_-11; v09)
   - specific decline reason, exact limit, override a decline (POLICY_-12 L10-12; v05)
   - fee dispute / waiver demand beyond the automatic rule (POLICY_-03 L11-12; POLICY_-10)
   - what was already reported to a bureau / credit-report correction (POLICY_-07 L11-12)
   - merchant-approved refund not received after >10 business days (POLICY_-04 L13-14) — *only* if data shows >10 bd elapsed; none currently do
   - updating/ruling on an existing dispute (POLICY_-05 L13) — e.g. u001 ord_3001
   
   **Content rule (v05, v06, v09):** an escalate answer = handoff statement **plus** the general policy the assistant *is* allowed to explain (dispute 90-day/15-day/pause windows; general limit factors; password + 2FA). It must NOT: promise outcomes, pause/waive, state qualification, disclose limits, read back account details on fraud, or determine fraud. Include an explicit handoff phrase ("I'm escalating this to a human agent").
2. **`both`** — about the shopper's *own specific order* **and** a policy rule is needed to interpret it: reschedule eligibility/cost (v03, v04), refund timing/application (v10), failed-payment consequences on a named order, dispute pause status on a named order, fee applicability to their order.
3. **`tool`** — pure lookup of the shopper's own record, no policy interpretation: next payment date/amount (v01), remaining balance, order list/status. (Answer only from record; no general policy padding needed.)
4. **`policy`** — generic question answerable from docs alone, no personal data (v02, v08). **Must not** include order IDs or account data (v02 must_not `ord_`) — don't call the order tool.

Tie-breakers / INFERENCES (not specified by the package — flag in README):
- Mixed "policy + human action" ⇒ `escalate` (v06 precedent).
- Hostile/foreign/nonexistent order ID ⇒ refuse without leaking; recommend label `tool` (a lookup was the intent) — **OQ Q5**.
- Prompt-injection wrapper ⇒ route by the underlying request, ignore the injected instructions.
- Same-day reschedule / reactivation ⇒ not escalate (policy explicitly says no support action).
- Out-of-scope (non-Sezzle) ⇒ `policy` with a polite decline (INFERENCE).

---

## Recommendation
- Treat the golden cases as a **specification of content rules**, not just routes: escalate answers must still carry allowed policy facts; forbidden phrases are substring-matched even in negation — add a deterministic output validator for them (F-24) and a code-level user_id scope on the order tool (F-07). Do date/business-day math and "next upcoming installment" selection deterministically in the tool, let the LLM compose and route.
- Normalize the repo to the documented `data/` + `cases/` layout (copy files) and make paths configurable; declare order-level `reschedules_used` authoritative and the failed-future-date oddity as "retry pending" in README.
- Send the §2.3 questions (pick 4–5) at the start; log them as evidence of judgment.
- Budget: $0.0005/question ⇒ design for one small-model call (router + answer in a single structured call) with a larger-model fallback only for escalate/both — put this in the cost/latency ADR.

## Open questions
1. Missing `llm.py` / `mock_orders_api.py` and flat file names — intentional? Same data for hidden set?
2. Route scoring method and regex case-sensitivity.
3. Reviewer's execution environment (API key/provider).
4. Authoritative `reschedules_used` and meaning of `failed` installments due after `today`.
5. Expected route for foreign/nonexistent order IDs.
6. Whether prep time counts toward the 2-hour budget; whether holidays count in business-day math.
