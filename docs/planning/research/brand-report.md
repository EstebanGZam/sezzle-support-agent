# Sezzle brand & business research: what it means for the take-home assistant

Researched 2026-09-27 from public sources. Tags: **[V]** = verified at the linked source on 2026-09-27. **[U]** = unverified, an assumption, or inferred from a secondary source. All page summaries came through a fetch tool, so re-check any exact wording you plan to quote.

## 1. What Sezzle is and how it makes money
- **What it is:** a US/Canada buy-now-pay-later (BNPL) and payments platform. Its stated mission is to "financially empower the next generation". It is a Public Benefit Corporation and a certified B Corp, and uses the tagline "Payments with Purpose". **[V]** [investors.sezzle.com/about](https://investors.sezzle.com/about/), [B Lab](https://www.bcorporation.net/en-us/find-a-b-corp/company/sezzle/)
- **Revenue mix for FY2025, from the 10-K:**
  - Merchant and partner income was 29% of revenue. It is a percentage of GMV plus a fixed fee per transaction.
  - Subscriptions (Sezzle Premium and Sezzle Anywhere) were 22%.
  - The rest is consumer fees and other income.
  - Merchant payout timing depends on the integration. With a direct integration, merchants are paid upfront, minus fees. With the virtual card, merchants get the full price and fees are collected separately.
  - **[V]** [10-K FY2025](https://www.sec.gov/Archives/edgar/data/1662991/000166299126000016/szl-20251231.htm)
- **Scale in Q2 2026:** 3.16M active consumers (+10.5% YoY), 854k active subscribers (+76% YoY), GMV of $1.3B, revenue of $149.7M, and 97.2% of orders were repeat usage. New enterprise merchants included Gymshark, Poshmark and RockAuto. Newer products include SezzleCash and Sezzle Send. **[V]** [Q2 2026 8-K ex99.1](https://www.sec.gov/Archives/edgar/data/1662991/000166299126000124/sezl-20260806ex9901.htm). The detail comes via press summaries.
- **Why this matters for the assistant:** repeat subscribers are the core of the business. Support quality on failed payments, reschedules and refunds directly protects retention, so wrong answers or overpromises cost real money.

## 2. Products (current public site)
| Product | What it is | Status |
|---|---|---|
| Pay in 4 | 4 payments every 2 weeks. The site's disclosure example is a $300 loan with $75 down plus a $7.49 service fee, 45.0% APR. | [V] [sezzle.com/how-it-works](https://sezzle.com/how-it-works) |
| Pay in 5 | 5 payments; labeled "Most Popular". The how-it-works page says 0% APR with a paid subscription. The merchant disclaimer example says 33.3% APR with a service fee. | [V] same page; [merchant guidelines](https://sezzle.com/merchant-marketing-guidelines/) |
| Pay in 2 | $10 minimum. It can appear when a purchase is over the shopper's spending power or under the minimum for other plans. | [V] [help: Pay-in-2](https://shopper-help.sezzle.com/hc/en-us/articles/15589214821908-What-is-Pay-in-2-and-how-does-it-work) |
| Pay Monthly | 3–48 months at 0–35.99% APR, through WebBank or third-party lenders. | [V] how-it-works |
| Sezzle Anywhere | Subscription; a virtual card usable wherever Visa is accepted. | [V] |
| Sezzle Premium | Subscription giving access to 350+ big brands. | [V] |
| Virtual card (single- and multi-use) | Card for paying at non-integrated merchants. | [V] [help](https://shopper-help.sezzle.com/hc/en-us/articles/360049623612-How-do-I-use-the-multi-use-virtual-card) |
| Sezzle Up | Opt-in credit reporting. Late payments are reported and may hurt credit; score gains are not guaranteed. | [V] [help: Sezzle Up](https://shopper-help.sezzle.com/hc/en-us/articles/360046679912-How-does-Sezzle-Up-impact-my-credit) |

- **Loans are issued by WebBank or Sezzle.** **[V]**
- **Conflict flagged:** one fetch summarized Pay in 4 as running "over 8 weeks". The how-it-works page says 6 weeks, which matches 4 payments every 2 weeks. Treat 6 weeks as correct. **[U]** for the 8-week claim.

## 3. Segments
- **Shoppers:** millennials and Gen Z, budget-conscious, often thin-file (limited credit history). Subscribers are the highest-value group. **[V]** mission and IR pages; **[U]** for the "thin-file" characterization.
- **Merchants:** long-tail Shopify/SMB stores through enterprise brands. Restricted categories include firearms, adult content, tobacco/vaping, gambling, drug paraphernalia and regulated pharmaceuticals. **[V]** [merchant guidelines](https://sezzle.com/merchant-marketing-guidelines/)

## 4. Most common shopper support scenarios (from the help-center taxonomy)
The help center has five categories: account/security/subscriptions, products, placing a new order, existing orders & payments, and contact. **[V]** [shopper-help.sezzle.com](https://shopper-help.sezzle.com/hc/en-us)

- **Failed payments.**
  - Causes: insufficient funds, or an expired or incorrect payment method.
  - Fix: Active Orders → Make a Payment.
  - Allow at least 24h (one business day) for processing.
  - A failed-payment fee "may" apply. A late fee "may" also apply after the due date or grace period.
  - Due dates use Central Time.
  - Updated 2026-07-15. **[V]** [article](https://shopper-help.sezzle.com/hc/en-us/articles/360046782511-Why-did-my-payment-fail-and-what-do-I-do-to-fix-it), [fees article](https://shopper-help.sezzle.com/hc/en-us/articles/10254134138644-What-are-failed-payment-and-late-payment-fees)
  - **The current articles give no dollar amounts.** Older third-party snippets quote "$10 failure / $5 reschedule". **[U]/stale.** The assistant should never quote fees from memory.
- **Rescheduling.** Qualifying orders only. A fee "may" apply. Some orders can be rescheduled "up to three times". Rescheduling is blocked while any payment is failed or processing. **[V]** [article](https://shopper-help.sezzle.com/hc/en-us/articles/10208795854996-Why-can-t-I-reschedule-my-payment), updated 2025-08-07.
- **Refunds and returns.**
  - The merchant must initiate the refund.
  - Money goes back to the card on file within about 10 business days of the refund confirmation email.
  - Refunds can't go to prepaid cards.
  - **[V]** [article](https://shopper-help.sezzle.com/hc/en-us/articles/360046890251-How-do-refunds-work-for-returned-or-canceled-orders)
- **Disputes.**
  - Opened via "Get help with this order" within 90 days of purchase.
  - An internal team investigates and mediates with the merchant through a dispute portal.
  - Shoppers are asked to respond quickly to requests for information.
  - **[V]** [after opening](https://shopper-help.sezzle.com/hc/en-us/articles/10996680855572-What-happens-after-my-dispute-is-opened), [how disputes work](https://shopper-help.sezzle.com/hc/en-us/articles/360046172151-How-do-disputes-work). The 90-day figure comes from a search snippet: **[U]** until checked on the page.
- **Spending power / limits, minimums, credit-report disputes, and unenrolling from Sezzle Up.** **[V]** help-center section titles.
- **Fraud / unrecognized charges.** These are routed to support by email, not self-serve. **[V]** dispute article.

## 5. Brand values, voice and visual identity
- **Values:**
  - Transparency, inclusivity, empowerment and financial responsibility.
  - The 2020 rebrand came with the tagline "The Way Forward".
  - CEO quote: "transparency, diversity, and inclusivity".
  - **[V]** [rebrand coverage](https://www.logo-designer.co/fintech-company-sezzle-reveals-new-logo-design-and-branding/) (secondary source).
- **Voice, observed in help articles:**
  - Written in second person, with short, direct, instructional sentences.
  - Names exact UI paths ("Active Orders → Make a Payment").
  - Hedges on fees ("may be applied").
  - Uses no slang in support copy.
  - Marketing copy is more upbeat ("Pay Later, Earn Rewards, & Build Credit History").
  - **[V]**
- **Banned marketing claims, per the merchant guidelines:** "free money", "no credit check", "guaranteed approval", "0% APR", "never pay interest", "buy now, worry later", and "Sezzle financing/loan". Trigger terms require the Reg Z disclaimer. **[V]** [guidelines](https://sezzle.com/merchant-marketing-guidelines/)
- **Visual identity (description only):**
  - Purple-led gradient "S" badge, plus a wordmark.
  - Clean sans-serif type, lots of white space, soft glow or gradient accents.
  - **[V]/[U]:** the purple gradient is confirmed by rebrand coverage; the current site's palette was not confirmed.
  - The logo must not be recreated or altered; co-branding needs written approval. **[V]** [brand assets](https://sezzle.com/brand-assets/)

## 6. Financial-communication and accessibility context
- **Regulatory status:** the CFPB's May 2024 interpretive rule treated BNPL lenders as card issuers under TILA/Reg Z. It was withdrawn on 2025-05-12, and the CFPB said it will not reissue it. **[V]** [Federal Register](https://www.federalregister.gov/documents/2025/05/12/2025-08286/interpretive-rules-policy-statements-and-advisory-opinions-withdrawal), [CFPB BNPL page](https://www.consumerfinance.gov/compliance/compliance-resources/consumer-cards-resources/buy-now-pay-later-bnpl-products/)
- **What still applies:** dispute and refund expectations, UDAAP (the ban on unfair, deceptive or abusive practices), and state law. Sezzle's own Reg Z-style disclaimers show it treats disclosures conservatively. **[U]** that this reflects legal posture rather than marketing caution.
- **Implications for the assistant:**
  - Use plain language, show exact amounts and dates, and never imply guaranteed approval, credit-score improvement or fee waivers.
  - Treat hardship or distress signals and credit-report disputes as escalation candidates.
  - For accessibility, keep sentences short, avoid jargon, write dates out ("July 15, 2026"), and never rely on color alone in any UI.

## (a) How the take-home mirrors real Sezzle support
| Real Sezzle scenario | Take-home equivalent |
|---|---|
| Help-center articles (FAQ answers) | the 12 policy docs → route `policy` |
| Dashboard views (order/installment status) | mock accounts JSON with the `today` date frozen at 2026-07-01 → route `tool` |
| "Why can't I reschedule?" (policy + account state) | route `both` |
| Disputes, fraud, credit-report errors, hardship, refunds the merchant must issue | route `escalate`. These map to the real "Get help with this order" form and the email-only support paths. |
| Fees "may" apply; amounts change (2026 articles dropped the $ figures) | why policy docs must be the only source: model memory of Sezzle fees is stale |
| Account-specific data | authorization: only answer about the `user_id` in the request |

## (b) Tone and voice rules for the system prompt
1. Speak directly to the shopper as "you". Use short, plain sentences, roughly 8th-grade reading level, with no finance jargon unless the policy doc uses it.
2. Lead with the answer (yes/no/amount/date), then give at most 2–3 short supporting steps.
3. **Quote amounts, dates, counts and fees only from the provided policy docs or tool results.** If they aren't there, say you don't have that detail. Never use outside knowledge of Sezzle.
4. Keep the policy's hedging: if the doc says a fee "may" apply, don't say "will", and the reverse.
5. Never promise outcomes you can't control: no fee waivers, approvals, limit increases, refund timing beyond the doc, dispute results or credit-score effects.
6. Never use Sezzle's banned claims: "free money", "no credit check", "guaranteed approval", "0% interest" as a blanket claim, or "worry later".
7. Be warm but not chirpy: acknowledge frustration in one clause, with no emojis, exclamation marks or sales upsell in support replies.
8. Only discuss the authenticated user's own orders. Never confirm or deny data about anyone else.
9. When escalating, say what will happen next and why, calmly, without blame, e.g. "This needs our support team because it involves a disputed charge".
10. Write dates in full ("July 15, 2026") and money with two decimals ("$42.50"). Treat "today" as the frozen dataset date.
11. Don't sound like an official Sezzle agent. Call yourself a support assistant and don't claim to be a person.
12. Where a doc provides it, give the in-app path ("Active Orders → Make a Payment") as the action step instead of vague advice.

## (c) Is a UI worth building?
**Mostly no.** The graded contract is the CLI `run_cases.py`, and a UI scores nothing on the rubric (scaffolding is explicitly "not graded") while eating a ~2h budget.

If there's time left over, the only worthwhile UI is a **≤30-minute single-file demo** (Streamlit/Gradio or one HTML page over the same pipeline). It would show the user picker, the route badge (policy/tool/both/escalate) and the cited doc/tool calls. That makes the grounding visible, which *is* graded.

To make it brand-inspired without impersonating Sezzle:
- Use a generic name ("Shopper Support Demo — synthetic data").
- Use no Sezzle logo, badge, wordmark or font.
- Use a neutral palette with at most one violet accent, not a gradient "S".
- Add a footer: "Unofficial take-home prototype; not affiliated with Sezzle; synthetic data".
- Keep it local only, with no public deploy. The brief asks not to post the challenge publicly.

## Recommendation
- Put rules 1–12 into the system prompt, with rules 3–5 enforced by structure as well: answers built from retrieved doc IDs and tool outputs only, plus a post-check that every $ amount and date in the answer appears in the retrieved context.
- Route disputes, fraud, credit-report and hardship requests, and other-user requests to `escalate`.
- Skip the UI unless everything graded is finished; if you build one, follow the de-branded plan above.
- One line in the README can note the real-world parallel (help center + dashboard + dispute form). It shows domain understanding at no cost.

## Open questions
- Do the 12 policy docs state fee amounts or reschedule limits that differ from the current public Sezzle pages? If so, the docs win; mention this in an ADR as the reason for not using model knowledge.
- Should hardship or distress language always escalate, or only when combined with an account action? Check the policy docs.
- Is the 90-day dispute window in the assessment docs? It's unverified on the public page here.
- Does the reviewer want any demo surface at all? The brief says no, so assume no.
