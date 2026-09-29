# P-008 — Owner decision: investigate and adopt a free inference provider (verbatim, user → lead)

- Date: 2026-09-28
- Tool/agent: Claude Code (lead orchestrator, Opus 5.5)
- Category: Planning prompt — **owner decision record**
- Note: the same message ended with a line `bash /tmp/claude-1000/dispatch-rg.sh`, outside the quoted brief. The lead inspected that script: it dispatches an agent on an unrelated project. It was **not executed**, pending the owner's confirmation.

---

I have reviewed the Gemini provider failures and the partial results from evaluation 003.

I am making an engineering decision to investigate and adopt a compatible free inference provider for this assessment.

This decision is motivated by my available budget and the observed provider instability, not by a failure to consider the security and privacy advantages of paid inference.

I understand and accept the trade-offs of free inference, subject to the assessment's confidentiality requirements and the provider's applicable terms.

## 1. Provider strategy

Investigate GroqCloud as the first alternative.

Evaluate its available free models, prioritizing GPT-OSS 120B if the actual account quota and capabilities are suitable.

Consider other free providers if Groq cannot meet the requirements.

Verify:

- Tool calling.
- Structured output compatibility.
- Python integration.
- Free quotas.
- Latency.
- Data retention and training policies.
- Model availability.
- Compatibility with the current evaluation pipeline.

Do not assume Gemini-specific SDK behavior is portable.

Preserve the existing Gemini implementation and introduce a minimal provider abstraction where necessary.

Do not rewrite the application architecture merely to switch providers.

## 2. Confidentiality and data handling

The assessment uses synthetic order data, but this does not automatically establish that all supplied materials are unrestricted.

Review the assessment's confidentiality instructions.

Verify the chosen provider's current data-handling conditions before transmitting assessment materials.

Do not send credentials, private repository contents, internal development logs, or unrelated confidential information.

Use the minimum authorized context required for inference.

Document the accepted privacy trade-offs and remaining risks.

If the assessment prohibits a proposed external use, do not proceed with that use.

## 3. Evaluation incident

Preserve evaluation 003 unchanged.

Record the Gemini 503/504 incident separately from application-level failures.

Do not treat infrastructure failures as evidence that the assistant's reasoning, grounding, or routing is incorrect.

Continue improving behavior using the cases that received valid responses and deterministic tests.

When a compatible provider is available, rerun the evaluation and preserve the new results.

Do not replace or overwrite historical runs.

## 4. Implementation boundaries

Maintain the approved architecture:

- Python CLI contract.
- Functional LLM in the pipeline.
- Controlled read-only tools.
- Server-side authorization.
- Policy-grounded responses.
- Structural security controls.
- Output validation.
- Safe escalation.

Adapt the provider integration without weakening security or changing the assessment's required output contract.

Do not hardcode answers for the visible cases.

Do not introduce unnecessary frameworks.

## 5. Engineering decision record

Document this as an owner-approved decision.

Include:

- The budget constraint.
- Observed Gemini availability failures.
- Paid and free alternatives considered.
- Provider capabilities and limitations.
- Privacy and confidentiality implications.
- Reason for selecting the provider.
- Evidence that would cause us to reconsider.
- Actual evaluation results after migration.

Respect the assessment's requirement for exactly three primary ADRs.

If this decision does not belong in one of those three, place it in the supplementary engineering decision log rather than adding a fourth ADR.

## 6. Next action

First, provide a concise recommendation for the free provider and model.

Identify any technical incompatibilities with the existing implementation.

Prepare the necessary provider adapter and deterministic tests.

Do not run the full real assessment evaluation until I have configured the new API key and the applicable data-handling conditions have been checked.

Do not overwrite the Gemini implementation.

Preserve all prompts, changes, and test results.

Continue the planned behavioral iteration without waiting for Gemini service recovery.

All technical documentation must be written in English. Communicate findings to me in Spanish.
