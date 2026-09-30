# P-006 — Implementation authorization (verbatim, user → lead)

- Tool/agent: Claude Code (lead orchestrator, Opus 5.5)
- Category: Planning prompt — **owner authorization record**

---

You are now authorized to execute the approved implementation plan.

## 1. Implementation authorization

Proceed with IP-01 and E-01 according to the approved specifications.

Use:

- Orchestrator as technical coordinator.
- Claude Code as the primary implementer.
- An independent evaluation agent working on isolated files.
- Codex as an independent reviewer.

Follow the approved architecture, specifications, acceptance criteria, and scope priorities.

Do not reopen settled architectural decisions unless implementation reveals a concrete conflict or significant technical risk.

## 2. Execution methodology

Follow Spec-Driven Development.

For each implementation stage:

1. Read the relevant specifications.
2. Implement the authorized scope.
3. Run the applicable tests.
4. Verify acceptance criteria.
5. Record the results.
6. Commit meaningful completed changes using Conventional Commits.
7. Report significant deviations or blockers.

Preserve a working application throughout development.

Do not introduce unnecessary frameworks or infrastructure.

## 3. Evaluation and iteration

The evaluation process is a critical assessment deliverable.

Preserve the first real evaluation run without modifying its results.

Identify actual failures, classify them, implement justified improvements, and perform the final evaluation.

Do not optimize exclusively for the visible golden cases.

Keep the independent holdout isolated until its designated evaluation stage.

Record model usage, latency, observed behavior, and evaluation results.

Do not fabricate measurements or replace historical evidence.

## 4. Gemini configuration

Use the approved primary and fallback models.

The application must read GOOGLE_API_KEY securely from its environment.

I will provide the credential through the local environment.

Do not print, expose, copy, or commit credential values.

Do not use the inherited GEMINI_API_KEY implicitly.

Do not make caching a prerequisite for successful execution.

If the credential is unavailable or the project's data-handling conditions remain unresolved, continue with deterministic tests and mocked LLM integrations.

Do not send assessment material to an unverified project.

## 5. Security requirements

Preserve the approved structural security controls.

Ensure authorization is enforced in application code.

Maintain isolation between users and independent requests.

Prevent unauthorized tool execution, cross-user data disclosure, unsupported actions, and unnecessary inference consumption.

Treat user input and tool-returned text as untrusted instructions.

Validate model outputs before returning them.

The assistant must remain within its authorized customer-support domain.

## 6. Git and documentation

Continue using the existing local repository and preserve its history.

Maintain:

- Conventional Commits.
- Requirements traceability.
- Prompt documentation.
- Architectural decision records.
- Evaluation artifacts.
- Honest implementation status.

Preserve this authorization prompt verbatim in the prompt log.

Do not create the GitHub remote or push the repository until the confidentiality and credential checks have passed and I explicitly authorize publication to the private remote.

## 7. Execution boundaries

I will personally manage assessment time.

You do not need to manage or report my clock.

Do not deploy infrastructure.

Do not launch optional Claude Cloud sessions.

Do not introduce functionality unrelated to the assessment.

Prioritize correctness, security, evaluation, and required deliverables over optional enhancements.

## 8. Reporting

Proceed with the approved implementation tasks.

Report progress at meaningful checkpoints, especially after:

- The first working end-to-end execution.
- The initial evaluation.
- The documented improvement.
- The independent code review.
- The final evaluation.

If a material architectural decision requires revision, present the evidence and proposed change for my approval.

Otherwise, continue executing the approved plan without requesting permission for every individual coding task.

All technical artifacts and commit messages must remain in English.

You are authorized to begin implementation now.
