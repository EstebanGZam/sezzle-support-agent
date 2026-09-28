# Deploying the support-assistant demo for ~21 days: options, cost, runbook

Researched 2026-09-27 from official pages, all fetched today. **V** = verified on the cited page. **A** = my assumption or general knowledge that I did not re-check today.

## 0. Is a public deployment even worth it?

**It adds almost no grading value, and it does add risk.**
- The brief does not require a deployment. Scaffolding, provider choice and LOC are not graded (**V**, shared brief). Reviewers grade by running `run_cases.py` locally on a hidden set. A URL does not help them do that.
- Risks of a public URL:
  - It goes against "don't post the challenge or your solution publicly".
  - Anyone who finds the URL can spend your Gemini budget.
  - Prompt-injection attempts on an open endpoint.
  - One more thing that can break during review, e.g. a cold-start 502 on free tiers.
- If you deploy anyway, make it **private-by-default**: either IAM-gated, or protected by a shared-secret header that goes only to the reviewer in the private repo README. Treat it as an optional "try it" convenience, never a dependency. The zip or private repo must stay fully self-sufficient.
- Given the ~2 h budget, time spent on deployment is time not spent on ADRs and the eval loop. **Default recommendation: don't deploy.** If you do, spend ≤20 min.

## 1. Platform comparison

| | **Google Cloud Run** | **Render Free** | **Koyeb Free** | **HF Spaces** | **Fly.io / Railway** |
|---|---|---|---|---|---|
| Free allowance | 2M req, 180k vCPU-s, 360k GiB-s, 1 GB NA egress per month (**V**, [free features](https://docs.cloud.google.com/free/docs/free-cloud-features)) | 750 instance-h/workspace/month (**V**, [render.com/docs/free](https://render.com/docs/free)) | 1 free instance per org, 0.1 vCPU / 512 MB, Frankfurt or Washington DC only (**V**, [koyeb instances](https://www.koyeb.com/docs/reference/instances)) | CPU Basic (2 vCPU / 16 GB) is free, **but creating a Docker or Gradio Space now requires a PRO plan**. Static Spaces are free (**V**, [HF Spaces overview](https://huggingface.co/docs/hub/spaces-overview)) | Fly: the pricing page lists no free tier, only a trial; shared-1x-256MB ≈ $2–4/mo (**V**, [docs.fly.io pricing](https://docs.fly.io/about/pricing/)). Railway: one-time $5 trial credit, Hobby $5/mo (**V**, [railway plans](https://docs.railway.com/reference/pricing/plans)) |
| Idle / cold start | min-instances=0 scales to zero; cold start is a few seconds for slim Python (**A**) | Spins down after 15 min idle; **~1 min** to restart (**V**) | Scales to zero after 1 h idle; cold start not documented (**V**) | Free hardware sleeps "after a period" (**V**, length not stated) | — |
| Hosting cost for 21 days | **$0** at demo volume (see §2) | $0 | $0 | $0 needs a PRO subscription | Fly ~$2–3; Railway $0–5 |
| Docker / Python | Yes (`--source` builds via Cloud Build: 2,500 free build-min/mo; Artifact Registry 0.5 GB free) (**V**) | Yes, native Python or Docker (**A**) | Yes (**A**) | Docker SDK (paid) (**V**) | Yes |
| Secrets | Secret Manager: 6 active versions and 10k accesses/mo free (**V**) | Dashboard env vars/secret files (**A**) | Encrypted secrets (**A**) | Space Secrets (**V**) | Env secrets |
| GitHub auto-deploy | Needs a Cloud Build trigger (more setup) (**A**) | Built in (**A**) | Built in (**A**) | Git push to the Space repo (**V**) | Built in |
| HTTPS / logs | Managed HTTPS on `*.run.app`, Cloud Logging (**A**) | Yes / dashboard logs (**A**) | Yes (**A**) | Yes | Yes |
| **Private-by-default** | **Yes: IAM-only (no `allUsers` invoker)**. The reviewer uses an identity token or `gcloud run services proxy` (**V**, [developer auth](https://docs.cloud.google.com/run/docs/authenticating/developers)) | No. The URL is public, so you need app-level gating | No (app-level gating only) | Private Space = only owner and collaborators, others get 404 (**V**) | App-level only |
| Spend protection | `--max-instances`. Budgets are **alerts only and don't cap spend**; spend-cap budgets are in *preview*; you can wire Pub/Sub to disable billing (**V**, [budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets)) | Free tier suspends instead of billing if no card is on file (**V**) | — | — | Railway usage limits (**A**) |

**Cloud Run caveats:**
- IAM-only access forces the reviewer to have a Google account plus the gcloud CLI, or to receive a service-account key. That is too much friction for a reviewer.
- The realistic reviewer-friendly option is a public URL plus a shared-secret header (`X-Demo-Key`), stored in the private repo README.
- Cloud Run needs a billing account linked to the project (**A**). The $300 trial credit is valid for 90 days (**V**).

**Render caveats:**
- The ~1-minute cold start is bad for a live demo.
- There is no private option.

## 2. 21-day cost estimate

Gemini paid tier (**V**, [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing), last updated 2026-09-24):
- **Gemini 3.8 Flash**: $0.75 in / $3.75 out per 1M tokens, promo price through 2026-12-31. It doubles on 2027-01-01.
- **Gemini 3.5 Flash-Lite**: $0.30 in / $2.50 out.
- Free tier: "content used to improve our products". Avoid it for assessment content; paid tier content is not used.

Assumption: ~3k tokens per question, split 2.5k input / 0.5k output. That gives **$0.00375 per question on Flash** and $0.0020 on Flash-Lite.

| Scenario | Questions | Gemini (Flash) | Gemini (Flash-Lite) | Hosting (Cloud Run) | **Total** |
|---|---|---|---|---|---|
| Best | 200 | $0.75 | $0.40 | $0 (≈600 vCPU-s vs 180k free) | **≈$1** |
| Expected | 2,000 | $7.50 | $4.00 | $0 | **≈$4–8** |
| Bounded (abuse, app cap hit) | cap at 3,000 | $11.25 | $6.00 | $0 (max-instances=1) | **≤$12** |

**Without an app-level cap, cost is bounded only by Gemini's own limits**, which are coarse:
- Tier 1 has a $10 per 10-minute spend-based limit (**V**, [rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)).
- The tier cap is $250 (**V**, same page).
- That is exactly why a hard in-app counter matters.

Local-only runs for grading (hidden set of maybe 50–200 cases × a few iterations) cost well under $5.

## 3. Rate limiting and LLM spend caps (any platform)

1. **Shared-secret header or basic auth** on `/ask`. Return 401 without it. Put the key in the private README only.
2. **Hard global question counter**, e.g. 3,000. Stateless containers can't reliably hold it, so:
   - enforce it per instance and set max-instances=1, **or**
   - accept "per-instance cap × max instances" as the bound.
3. **Per-IP token bucket**, e.g. 10 req/min, in-process with no library needed. Plus `max_output_tokens` and an input-length limit (e.g. 1,000 chars).
4. **Dedicated Gemini API key/project** for the demo, with a billing budget alert at $5/$10/$20. Revoke the key at teardown.
5. `--max-instances=1 --concurrency=10 --timeout=30s` on Cloud Run.

## 4. Runbook for the recommended option: Cloud Run with a shared-secret header

All commands are **A**: standard `gcloud` syntax, not executed.

```bash
# Deploy (one time, ~10 min)
gcloud config set project $PROJECT; gcloud config set run/region us-central1
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com
printf %s "$GEMINI_API_KEY" | gcloud secrets create gemini-key --data-file=-
printf %s "$(openssl rand -hex 16)" | gcloud secrets create demo-key --data-file=-
# grant the runtime service account roles/secretmanager.secretAccessor on both secrets
gcloud run deploy sezzle-demo --source . --allow-unauthenticated \
  --min-instances 0 --max-instances 1 --concurrency 10 --timeout 30 --memory 512Mi \
  --set-secrets GEMINI_API_KEY=gemini-key:latest,DEMO_KEY=demo-key:latest
# Budget alert: Billing → Budgets → $10, alert at 50/90/100 % (alerts-only, not a cap)

# Private variant (no public exposure): drop --allow-unauthenticated, then
gcloud run services add-iam-policy-binding sezzle-demo --member=user:REVIEWER_EMAIL --role=roles/run.invoker
#   reviewer: gcloud run services proxy sezzle-demo --project $PROJECT   (V)

# Rollback
gcloud run revisions list --service sezzle-demo
gcloud run services update-traffic sezzle-demo --to-revisions REVISION_NAME=100
# Emergency kill switch (keeps the service, blocks all traffic):
gcloud run services update sezzle-demo --max-instances 0   # or remove allUsers invoker binding

# Teardown (day 21)
gcloud run services delete sezzle-demo
gcloud secrets delete gemini-key; gcloud secrets delete demo-key
gcloud artifacts repositories delete cloud-run-source-deploy --location us-central1
# Revoke the Gemini API key in AI Studio; or simply: gcloud projects delete $PROJECT
```

Before relying on `--max-instances 0` as the kill switch, check that it is accepted (**A**). The safe fallback is `gcloud run services remove-iam-policy-binding sezzle-demo --member=allUsers --role=roles/run.invoker`.

## Recommendation

1. **Don't deploy publicly.** Submit the zip or private repo. Reviewers grade locally, and a URL adds risk (posting publicly, spend abuse) but no graded value. Put a single `uvicorn` command in the README instead.
2. **If you want a live demo:**
   - Use **Cloud Run** (min=0, max=1) with a shared-secret header, an in-app cap of 3,000 questions, a dedicated paid-tier Gemini key, and a $10 budget alert.
   - Expected 21-day cost is **≈$4–8** (all Gemini), bounded at **≈$12**.
   - Tear it down on day 21 by deleting the project.
   - Use IAM-only if the reviewer is known to use gcloud.
3. **Model:** Gemini 3.5 Flash-Lite is the cheapest. 3.8 Flash stays cheap while its promo pricing lasts (to 2026-12-31). Pick whichever passes the evals; the cost difference here is a few dollars.
4. **Skip:**
   - Render: 1-minute cold starts, no private option.
   - HF Spaces: Docker needs PRO.
   - Fly and Railway: small but non-zero cost, no advantage.
   - Koyeb: acceptable fallback (0.1 vCPU, 1 h idle, public).

## Open questions

- Does the user already have a GCP project with billing enabled? If not, setup friction goes up (billing account plus the $300 trial).
- Is the reviewer expected to click a URL at all? Nothing in the brief says so.
- The Gemini model names and prices above come from today's pricing page. They differ from older naming, so re-check them on the day of the deploy.
- Render's secret, auto-deploy and log features, Koyeb's cold start, and Cloud Run's Python cold-start time were not verified on official pages today.
- Cloud Run "spend cap budgets" are in preview, so availability on the user's account is unknown.
