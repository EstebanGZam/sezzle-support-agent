# P-005 — Owner decisions for the final preparation phase (verbatim, user → lead)

- Tool/agent: Claude Code (lead orchestrator, Opus 5.5)
- Category: Planning prompt — **owner decision record**

---

I have reviewed the preparation package and the independent Codex review.

I approve the general engineering direction and authorize the final preparation phase, subject to the following clarifications.

I remain the engineer responsible for the technical and architectural decisions. Your role is to coordinate, document, challenge assumptions, implement and execute the approved direction.

## 1. Gemini validation correction

I independently validated my Gemini API access.

A generateContent request to gemini-3.8-flash returned HTTP 200, confirming successful authentication and model invocation.

The response included:

- modelVersion: gemini-3.8-flash
- serviceTier: standard
- finishReason: MAX_TOKENS

The empty response resulted from the low output-token limit.

This does not independently establish billing status, but it also does not support concluding that paid inference is unavailable.

I have not explicitly provided you with an API key during this assessment workflow.

Investigate which credential source was used during your previous smoke tests, without exposing credential values.

Distinguish inference availability from cache-storage quotas.

Update assumption A-10 and preserve the original observation alongside the revised interpretation.

Do not treat successful caching as a functional prerequisite.

I will manage and validate credentials locally.

## 2. Approved model configuration

Primary: gemini-3.5-flash-lite.

Fallback: gemini-3.1-flash-lite.

Keep model selection configurable and verify compatibility.

Do not automatically switch to an unpaid project with different data-handling conditions.

A second LLM provider is not required unless justified by the assessment or an identified compatibility requirement.

## 3. Architecture decisions

I approve the general architecture:

- Python 3.12 and the mandatory CLI contract.
- Native Google GenAI SDK.
- Controlled tool-calling orchestration.
- Full-context policy grounding.
- Stateless, isolated execution per case.
- Shared immutable knowledge resources.
- Read-only, user-scoped tools.
- Structured outputs and programmatic validation.
- Safe escalation and appropriate inference limits.

Do not introduce unnecessary frameworks, vector databases, or infrastructure.

The LLM must genuinely interpret requests, use authorized tools, reason over policies, and generate contextual answers.

Application code must enforce security, authorization, validation, and deterministic business invariants where appropriate.

Do not replace the LLM with hard-coded answers.

## 4. Agent recommendations

Review AR-01 through AR-08 and reconcile them with my approved direction.

I provisionally approve the policy_applied routing approach, narrow output validator, expanded escalation tripwire, and scope tiers.

Validate routing and security behavior against the official assessment requirements rather than overfitting to visible cases.

Document any remaining assumptions.

## 5. Repository and engineering standards

I approve the local repository structure and lightweight SDD approach.

Preserve original assessment materials and the provenance manifest.

Use:

- Private GitHub repository.
- Conventional Commits.
- Reproducible dependencies.
- Appropriate CI.
- AGENTS.md as the shared instruction source.
- CLAUDE.md referencing AGENTS.md.
- Requirements traceability.
- Documented architectural decisions.
- Complete prompt logging.
- Reproducible evaluation artifacts.

Do not create the remote repository or push confidential materials until the final confidentiality and credential checks are complete.

The final submission must also be independently executable as a ZIP.

## 6. Security and application scope

The assistant must operate exclusively within its authorized customer-support domain.

Implement proportionate structural safeguards against prompt injection, cross-user information leakage, unauthorized operations, out-of-domain requests, excessive inference consumption, and provider failures.

Preserve legitimate customer-support behavior.

Do not rely exclusively on system prompts for security.

## 7. Development agents

Approve:

- Orchestrator as technical coordinator.
- One primary implementation agent.
- One independent evaluation agent operating on separate files.
- Codex as independent reviewer.

Claude Cloud remains optional and outside the critical implementation path.

## 8. Time and deployment

I will personally track assessment time. You do not need to manage the clock.

Deployment remains an optional separate phase after the mandatory assessment deliverables.

Do not provision infrastructure yet.

## 9. Documentation and traceability

Preserve this message verbatim in the prompt log.

Update the assumptions register, engineering decision records, architecture specifications, and implementation plan to reflect my decisions.

Maintain a clear distinction between official requirements, my decisions, agent recommendations, and unresolved assumptions.

Do not fabricate execution evidence or rewrite historical results.

## 10. Next action

Complete the Gemini credential-provenance investigation using existing evidence and non-secret metadata.

Correct the affected documentation.

Present the final implementation-readiness checklist and identify only genuine remaining blockers.

Do not repeat the advisory phase.

Do not launch IP-01 or E-01 yet.

Do not begin application implementation until I explicitly authorize it.

All technical documentation must remain in English. Communicate findings to me in Spanish.
