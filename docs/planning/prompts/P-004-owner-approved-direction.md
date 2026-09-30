# P-004 — Owner-approved technical direction & SDD preparation phase (verbatim, user → lead)

- Tool/agent: Claude Code (lead orchestrator, Opus 5.5)
- Category: Planning prompt — **owner decision record** (these decisions are owner-approved, not agent-approved)

---

I have reviewed the technology decision matrix and the independent Codex review.

I am now establishing the following engineering direction as the project owner.

You remain responsible for technical coordination, specifications, and implementation planning. I retain final authority over architecture and technology selection.

## Approved technical direction

1. Repository: organize copies of the original assessment materials using the documented structure, preserving provenance and file integrity through a manifest. Keep the repository private.

2. Language: Python 3.12, with the required CLI contract. Do not introduce Spring Boot or a web framework unless a concrete requirement justifies it.

3. LLM orchestration: native Google GenAI SDK with an explicit, controlled tool-calling loop and a lightweight configuration abstraction.

4. Knowledge grounding: use the complete policy corpus initially. Do not introduce embeddings or vector infrastructure without measured justification.

5. Execution: use a stateless, isolated execution context per case. Shared resources should be initialized once and reused safely. Start with sequential execution while preserving a clean path toward bounded concurrency.

6. Security: implement structural controls, scoped read-only tools, strict authorization, controlled inference consumption, input/output validation, and safe escalation.

7. Model: use Gemini Flash-Lite. Compare the currently available compatible variants through a minimal smoke test and present the results before locking the primary model. Keep a configurable compatible fallback.

8. Evaluation: pytest, deterministic fake-model tests, reproducible LLM evaluations, local traces, and independent adversarial review.

9. Engineering: uv, dependency locking, Conventional Commits, lightweight SDD, private GitHub, and proportionate CI. Final delivery must also be possible as a self-contained ZIP.

10. Agents: Orchestrator as technical coordinator, one principal implementer, a separate evaluation agent, and Codex for independent review. Claude Cloud remains optional.

Deployment is not part of the mandatory implementation. Preserve the option of a protected 21-day demo as a separate subsequent phase.

## Important clarification: deterministic logic vs. LLM responsibility

Do not interpret the requirement for a working LLM as a prohibition on deterministic business-rule validation.

The LLM must genuinely interpret requests, use permitted tools, reason over authorized data and policies, and generate contextual responses.

Application code must enforce authorization, tool boundaries, validation, and business invariants where appropriate.

Use deterministic calculations when they improve correctness and safety without replacing the LLM with a hard-coded answering system.

The exact boundary should be documented as an architectural decision.

Do not overfit routing or business logic to the visible golden cases.

## Architecture and security requirements

The assistant is exclusively intended for the support domain described by the assessment.

It must not become a general-purpose assistant.

Consider prompt injection, cross-user data leakage, unauthorized order access, out-of-scope requests, unnecessary token consumption, and provider failures.

Legitimate support questions should continue to receive useful grounded responses.

Prefer enforceable application-level safeguards over prompt-only restrictions.

## Assumptions and traceability

Do not contact the hiring manager.

Record unresolved ambiguities as explicit assumptions, including their evidence, rationale, risk, and potential impact.

Maintain a clear distinction between official requirements and my own engineering choices.

Preserve the original advisory prompts, subsequent instructions, delegated agent prompts, and their relevant outcomes.

Document these decisions as owner-approved rather than agent-approved.

Respect Sezzle's required ADR format and deliverables.

I will personally manage assessment time. You do not need to manage the clock.

## Next authorized phase

Proceed with local repository-architecture documentation and lightweight SDD preparation.

Prepare:

- Final repository structure and assessment file organization.
- AGENTS.md and CLAUDE.md.
- Requirements and assumptions register.
- Specifications and acceptance criteria.
- Task decomposition with requirement traceability.
- Proposed architectural decision records.
- Security and evaluation design.
- Agent responsibilities.
- Sequential implementation prompts.
- Final implementation-readiness checklist.

You may create and organize local planning and documentation artifacts, preserving the original assessment materials.

Do not implement application functionality yet.

Do not create or publish the remote repository, deploy services, or expose assessment material to additional external systems without authorization.

Present the completed preparation package and identify any remaining decisions that genuinely require my approval.

All technical artifacts must be in English. Communicate the summary to me in Spanish.
