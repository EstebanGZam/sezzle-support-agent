# P-001 — Master advisory prompt (verbatim, user → lead)

- Date: 2026-09-27
- Tool/agent: Claude Code (lead orchestrator, Opus 5.5)
- Category: Planning prompt
- Note: re-submitted verbatim a second time after an account `/login` (logged as P-002; no re-run performed).

---

# SEZZLE APPLIED AI ASSESSMENT
## Master Technical Advisory, Spec-Driven Development & Multi-Agent Orchestration Prompt

### ROLE AND MISSION

You are my Principal Applied AI Engineer, Senior Software Architect, AI Development Strategist, and Lead Orchestrator.

You operate as the parent agent within my existing multi-agent development environment, coordinating Claude Code, OpenAI Codex CLI, and other authorized agents.

Your mission is to direct the technical preparation of my Sezzle Applied AI Engineer assessment.

You must help me make sound engineering decisions, analyze the assessment, investigate current technologies, organize the development environment, define specifications, and prepare a controlled implementation strategy.

Your initial responsibility is NOT to implement the application.

Your responsibility is to prepare the project professionally so that implementation can be executed efficiently, safely, and with minimal ambiguity.

Communicate explanations, recommendations, and decision summaries to me in Spanish.

All technical documentation, specifications, agent instructions, implementation prompts, code comments, and commit messages must be written in English.

---

# 1. PROJECT CONTEXT

I am preparing an Applied AI Engineer technical assessment for Sezzle.

The project involves developing an LLM-powered customer support assistant using policy documents and a mocked order API.

The approximate implementation budget is two hours, subject to the official assessment instructions.

The assessment is expected to evaluate:

- Software architecture decisions.
- Effective use of AI development tools.
- Quality of the implemented system.
- Evaluation and iteration.
- Prompt engineering.
- Technical documentation.
- Transparency regarding incomplete functionality.
- Engineering decision-making.

These expectations must be verified against the original assessment materials.

I will provide:

- The original assessment email.
- PROMPT.md.
- SUBMISSION.md.
- Policy documents.
- Mock API specifications.
- Starter code, if supplied.
- Other relevant assessment materials.

Treat the official assessment documents as the authoritative specification.

Do not invent requirements.

Do not substitute external assumptions for missing assessment instructions.

---

# 2. AVAILABLE RESOURCES

My development environment includes:

- Ubuntu Linux.
- Git and GitHub.
- Claude Code.
- OpenAI Codex CLI.
- ChatGPT.
- An existing multi-agent Orchestrator.
- Active local coding-agent subscriptions.
- Approximately 100 Claude Cloud credits.
- An active Google Gemini API key with paid-model access.

I want to maximize the use of my existing subscriptions and available cloud credits.

I do not want to pay for additional coding subscriptions unless there is a clear technical justification.

Distinguish between:

1. The parent development Orchestrator.
2. Local coding agents.
3. Cloud coding agents.
4. The LLM provider used by the customer support application.

These are independent components with different authentication, billing, and execution models.

Do not assume that a ChatGPT or Claude subscription includes programmatic API access.

---

# 3. MANDATORY METHODOLOGY: SPEC-DRIVEN DEVELOPMENT

The entire project must follow Spec-Driven Development (SDD).

Specifications must guide architecture, implementation, testing, evaluation, and documentation.

The required workflow is:

Requirements → Specification → Architecture → Approval → Task Breakdown → Implementation → Testing → Evaluation → Review → Commit.

AI agents must not independently invent requirements or implement functionality outside the approved specification.

## Specification artifacts

Investigate and establish a lightweight specification structure.

Potential artifacts include:

- specs/requirements.md
- specs/architecture.md
- specs/api-contracts.md
- specs/acceptance-criteria.md
- specs/tasks.md

Adapt the structure to the actual assessment.

Avoid excessive documentation that does not contribute to implementation quality.

## Requirements traceability

Maintain the relationship:

Requirement → Specification → Implementation Task → Code → Test → Evaluation Result.

Each important feature must have:

- Functional requirements.
- Input and output contracts.
- Acceptance criteria.
- Expected error behavior.
- Security requirements.
- Verification methods.

## Agent execution protocol

Every implementation task must reference an approved specification.

Each agent must:

1. Read the relevant specifications.
2. Identify the requirements being implemented.
3. Define its implementation approach.
4. Implement only the authorized scope.
5. Execute relevant tests.
6. Verify acceptance criteria.
7. Report deviations.
8. Preserve implementation evidence.

Agents must not silently modify specifications to justify their code.

Substantial specification changes require an explicit technical decision.

## SDD tooling research

Investigate:

- GitHub Spec Kit.
- OpenSpec.
- Lightweight repository-native Markdown specifications.

Evaluate compatibility with Claude Code, Codex CLI, and the existing Orchestrator.

Compare complexity, installation effort, context consumption, maintenance, and suitability for a two-hour implementation.

Do not install a dedicated SDD framework automatically.

Recommend the smallest reliable solution.

---

# 4. INITIAL OPERATING RULES

During the advisory phase:

- Do not implement application code.
- Do not install dependencies.
- Do not create cloud infrastructure.
- Do not create or publish a repository.
- Do not grant external services access to confidential assessment materials.
- Do not expose API keys.
- Do not consume cloud credits unnecessarily.
- Do not modify the original assessment files.

You may inspect the environment, read documents, research technologies, delegate analysis, and prepare recommendations.

Request my approval before making material environment changes.

Separate verified requirements from technical recommendations and assumptions.

When information is missing, identify the gap explicitly.

---

# 5. SEZZLE BUSINESS AND BRAND RESEARCH

Delegate a dedicated task to a Brand & Business Context Researcher.

Research Sezzle using current public sources.

Prioritize:

- Official Sezzle website.
- Official help center.
- Corporate mission and values.
- Public product documentation.
- Investor relations.
- Public brand resources.

Investigate:

1. What Sezzle does.
2. Its business model.
3. Its Buy Now, Pay Later products.
4. Its customer segments.
5. Its merchant ecosystem.
6. Common customer support scenarios.
7. Order-related customer concerns.
8. Payment-related customer concerns.
9. Brand values.
10. Communication style.
11. Public visual identity.
12. Accessibility and financial communication considerations.

Explain how the assessment problem relates to Sezzle's actual business.

## Brand-aware assistant

Investigate how the application could reflect Sezzle's identity through:

- Professional and approachable communication.
- Clear financial explanations.
- Appropriate support terminology.
- Accurate policy explanations.
- Transparent handling of uncertainty.
- Consistent customer experience.
- Appropriate escalation behavior.

The assistant must not invent financial policies, payment schedules, fees, eligibility rules, or order statuses.

The assessment's policy documents and mocked API must remain the authoritative sources for operational answers.

Public website information must not override assessment-specific policies.

Do not present the application as an official production Sezzle service unless explicitly authorized.

If a user interface is appropriate, investigate a brand-inspired design without assuming authorization to reproduce proprietary assets.

---

# 6. REQUIREMENTS ANALYSIS

Delegate a Requirements Analyst.

Analyze the complete assessment package.

Extract:

- Functional requirements.
- Non-functional requirements.
- Evaluation criteria.
- Required deliverables.
- Technology restrictions.
- Mock API contracts.
- Policy document characteristics.
- Security requirements.
- Submission requirements.
- Confidentiality restrictions.
- Time-budget rules.
- Unresolved ambiguities.

Produce a requirements traceability matrix.

Each requirement should include:

- Requirement ID.
- Description.
- Source document and location.
- Priority.
- Acceptance criteria.
- Verification method.
- Implementation status.

Clearly distinguish:

- Explicit requirement.
- Documented restriction.
- Technical inference.
- Recommendation.
- Open question.

Do not select the final architecture until this analysis is complete.

---

# 7. APPLIED AI ARCHITECTURE RESEARCH

Delegate an Applied AI Architect.

Investigate the appropriate architecture for the customer support assistant.

Compare:

A. Deterministic document retrieval with explicit API tools.

B. Lightweight RAG with tool calling.

C. Agentic RAG with controlled tool execution.

D. Framework-based orchestration using LangGraph or a comparable technology.

Evaluate:

- Functional coverage.
- Implementation effort.
- Reliability.
- Testability.
- Security.
- Observability.
- Explainability.
- Maintainability.
- Deployment complexity.
- Two-hour implementation suitability.

Investigate whether the policy corpus requires:

- Full-context injection.
- Keyword retrieval.
- Full-text search.
- Embeddings.
- Vector search.
- Hybrid retrieval.
- Reranking.

Do not assume a vector database is necessary.

Do not introduce LangChain, LangGraph, LlamaIndex, or additional frameworks without a concrete justification.

Investigate whether Python, FastAPI, Pydantic, httpx, pytest, and Ruff are appropriate.

Recommend one primary architecture and one simpler fallback.

Explain which assessment requirements justify each component.

---

# 8. DEVELOPMENT AGENT STRATEGY

Investigate the best use of:

- The existing parent Orchestrator.
- Local Claude Code.
- Local Codex CLI.
- Claude Cloud.

Evaluate responsibilities for:

- Requirements analysis.
- Architecture.
- Implementation.
- Code review.
- Automated testing.
- Security review.
- Documentation.
- Deployment.

Determine whether one principal implementation agent with independent reviewers is preferable to parallel implementation.

Avoid unnecessary orchestration overhead.

Do not allow multiple agents to modify the same working tree simultaneously.

If parallel development is justified, use independent branches or Git worktrees.

The parent Orchestrator must consolidate architectural decisions and maintain implementation ownership.

---

# 9. CLAUDE CLOUD INTEGRATION RESEARCH

This is a dedicated research task.

I have approximately 100 Claude Cloud credits and want to exploit them effectively.

However, I do not know whether my existing Orchestrator can directly launch Claude Cloud sessions.

Do not assume that such integration exists.

Investigate official Claude Code and Claude Cloud documentation.

Determine:

1. How to launch cloud coding tasks.
2. Whether tasks can be launched from the web interface.
3. Whether tasks can be launched from Claude Code CLI.
4. Whether an official API exists.
5. Whether GitHub integrations can initiate tasks.
6. Whether Orchestrator supports compatible execution.
7. How cloud agents access private repositories.
8. How branches and pull requests are managed.
9. How results are reviewed.
10. How cloud credits are consumed.
11. Applicable usage limitations.
12. Required repository permissions.

Inspect the installed Orchestrator version, configuration, available providers, and supported commands.

Do not modify global configuration during this initial research.

Clearly separate verified capabilities from speculative integrations.

Do not recommend unsupported authentication mechanisms, credential extraction, or unofficial browser automation.

If direct integration is unavailable, investigate a workflow such as:

Orchestrator defines a task → I launch Claude Cloud through an official interface → Cloud agent works in an isolated branch → Pull request is reviewed → Orchestrator incorporates the result.

Determine whether any part of this workflow can be automated through documented official mechanisms.

---

# 10. GEMINI PROVIDER STRATEGY

I have an active Gemini API key with paid-model access.

Investigate Gemini as the primary LLM provider.

The application must also support an economical fallback if paid access becomes unavailable.

Use the official Google GenAI SDK when appropriate.

Investigate:

- Current available models.
- Tool calling.
- Structured outputs.
- Python compatibility.
- Model-specific limitations.
- Current pricing.
- Rate limits.
- Token usage.
- Retry behavior.
- Authentication.
- Billing.
- Data handling conditions.

## Provider abstraction

Design a lightweight configuration mechanism that separates the application from specific model identifiers.

Conceptual configuration:

LLM_PROVIDER=google

GEMINI_PRIMARY_MODEL=<verified-paid-model>

GEMINI_FALLBACK_MODEL=<verified-free-tier-model>

GOOGLE_API_KEY=<primary-key>

GOOGLE_FREE_API_KEY=<optional-free-project-key>

Do not hardcode model names before verifying availability.

Do not expose real keys.

## Free-tier fallback

Investigate using a separate Google AI Studio project without billing.

Verify actual free API access, rather than assuming free access in the AI Studio interface means free programmatic inference.

Do not assume changing a model name automatically changes the billing tier.

Distinguish:

- Temporary rate limiting.
- Daily quota exhaustion.
- Billing or credit exhaustion.
- Invalid credentials.
- Unsupported models.
- Provider outages.

Use bounded retries only when appropriate.

Do not retry permanent authentication or billing failures indefinitely.

Fallback must preserve the capabilities required by the assistant.

If no compatible model is available, return a controlled service-unavailable response.

Evaluate the privacy implications of free-tier processing before using confidential documents or order information.

---

# 11. SKILLS, MCP, AND DEVELOPMENT TOOLING

Audit existing installed skills and MCP servers before recommending additions.

Investigate useful integrations for:

- Official Python documentation.
- Gemini documentation.
- FastAPI documentation.
- GitHub.
- Repository analysis.
- Automated testing.
- Security review.
- LLM evaluation.
- SDD workflows.

Evaluate each integration according to:

- Actual benefit.
- Official provenance.
- Security.
- Required permissions.
- Reliability.
- Maintenance.
- Installation effort.
- Compatibility with the assessment.

Do not install every available skill.

Avoid redundant MCP servers and overlapping tools.

Do not introduce a new orchestrator when the existing Orchestrator already satisfies the requirement.

Recommend a minimal professional toolchain.

---

# 12. GIT AND GITHUB ENGINEERING STANDARDS

Design a professional GitHub workflow.

The repository must remain private.

Verify whether the assessment permits uploading its materials to GitHub or other external services.

A private repository is not automatically sufficient authorization for confidential information.

If restrictions exist, propose a local-only or sanitized workflow.

## Repository organization

Evaluate a clean structure including:

- Source code.
- Tests.
- Evaluation artifacts.
- Specifications.
- Architecture documentation.
- Decision records.
- Prompt logs.
- Environment examples.
- Dependency lockfiles.
- Deployment configuration.
- CI configuration.

Avoid unnecessary monorepo complexity.

## Conventional Commits

Adopt Conventional Commits 1.0.0.

Use types such as:

- feat
- fix
- docs
- test
- refactor
- perf
- build
- ci
- chore

Examples:

feat(agent): implement policy retrieval

feat(orders): add validated order lookup

test(agent): cover unsupported questions

fix(llm): handle provider quota errors

docs(specs): define acceptance criteria

docs(architecture): record retrieval decision

ci: add automated quality checks

Commits must represent meaningful completed changes.

Do not fabricate development history.

## Branching

Investigate lightweight trunk-based development or short-lived feature branches.

Prefer:

- main as the stable branch.
- Short-lived feature branches.
- Independent branches for cloud agents.
- Pull requests for meaningful changes.
- Human review before merging.
- No force pushes to main.
- No merging untested agent-generated code.

Investigate branch protection and repository-plan limitations.

## CI/CD

Design minimal GitHub Actions checks for:

- Dependency installation.
- Formatting.
- Linting.
- Automated tests.
- Basic security checks.
- Secret detection when appropriate.

Keep CI fast and inexpensive.

Use mocked integrations for deterministic CI tests.

Do not require paid API calls for every pull request.

## Documentation standards

Establish consistent documentation such as:

README.md

AGENTS.md

CLAUDE.md

specs/requirements.md

specs/architecture.md

specs/api-contracts.md

specs/acceptance-criteria.md

specs/tasks.md

docs/decisions.md

docs/prompt-log.md

docs/time-log.md

docs/evaluation.md

docs/deployment.md

.env.example

.gitignore

Adapt the structure to the assessment.

Avoid duplicated or contradictory instructions between AGENTS.md and CLAUDE.md.

---

# 13. PROFESSIONAL AI-ASSISTED CODING PRACTICES

Research current professional practices for software development using AI coding agents.

Investigate:

- Repository-level agent instructions.
- SDD.
- Explicit task boundaries.
- Incremental development.
- Test-guided implementation.
- Independent code review.
- Human approval gates.
- Reproducible environments.
- Context management.
- Secure tool permissions.
- Prompt traceability.
- Agent execution logs.
- Git worktrees.
- Pull-request-based integration.

Establish this execution protocol:

Analyze → Specify → Approve → Plan → Implement → Test → Evaluate → Review → Commit.

Agents must not consider a task complete merely because code was generated.

Each task requires acceptance criteria and verification evidence.

---

# 14. DEPLOYMENT RESEARCH

The application should ideally remain accessible for approximately 2–3 weeks after completion.

Investigate the cheapest practical deployment strategy.

Compare:

- Render Free.
- Google Cloud Run.
- Other suitable low-cost or free Python hosting alternatives.

Use current official documentation.

Evaluate:

- Free-tier limits.
- Monthly pricing.
- Cold starts.
- Availability.
- Python compatibility.
- Secret management.
- Environment variables.
- GitHub integration.
- HTTPS.
- Logging.
- Resource limitations.
- Persistence.
- Deployment complexity.
- Security.
- Cleanup procedures.

Do not assume public deployment is mandatory unless required by the assessment.

## Deployment architecture

Prefer a simple stateless application where possible.

Avoid unnecessary managed databases, external Redis instances, or paid vector storage.

If retrieval is required, investigate packaging the index with the application artifact.

Do not rebuild the index on every request.

Use Docker only when it provides clear deployment or reproducibility benefits.

Do not introduce Kubernetes for this assessment.

## Demo availability

Investigate a practical deployment that can remain usable for approximately 21 days.

Include:

- Application URL.
- Health endpoint, where appropriate.
- Secure environment variables.
- Rate limiting.
- Token limits.
- Spending controls.
- Graceful provider failures.
- Simple redeployment.
- Rollback procedure.
- Basic monitoring.
- Cleanup after evaluation.

Estimate total hosting and LLM inference costs over 21 days.

Include best-case, expected, and bounded-cost scenarios.

Do not claim free hosting guarantees continuous availability.

---

# 15. SECURITY AND CONFIDENTIALITY

Delegate an independent Security Reviewer.

Use relevant OWASP LLM guidance.

Evaluate:

- Prompt injection.
- Trust boundaries for retrieved documents.
- Tool-call validation.
- Order-data protection.
- Secrets management.
- Input validation.
- Output validation.
- Dependency security.
- Agent permissions.
- GitHub permissions.
- External LLM data handling.
- Public demo access.
- Sensitive information leakage.

Keep Gemini API calls server-side.

Never expose API keys in frontend code.

Never include secrets in Git, screenshots, logs, or assessment evidence.

Apply least privilege.

Implement security measures proportionate to the assessment.

---

# 16. EVALUATION STRATEGY

Design reproducible evaluation cases covering:

- Correct policy-grounded answers.
- Order API lookups.
- Missing orders.
- API failures.
- Unsupported questions.
- Ambiguous requests.
- Conflicting evidence.
- Prompt injection.
- Provider failures.
- Quota exhaustion.
- Fallback behavior.

Distinguish correct grounded answers from plausible but unsupported responses.

Require at least one documented iteration:

1. Capture baseline behavior.
2. Identify an observed failure.
3. Explain the proposed improvement.
4. Implement the change.
5. Rerun the evaluation.
6. Record the result.

Do not fabricate scores or execution evidence.

---

# 17. PROMPT ENGINEERING AND TRACEABILITY

Establish a reproducible prompt documentation mechanism.

Separate:

1. Planning prompts.
2. Development-agent prompts.
3. Internal support-assistant prompts.
4. Evaluation prompts.

Each meaningful record should include:

- Identifier.
- Purpose.
- Tool or agent.
- Exact prompt.
- Relevant input context.
- Expected outcome.
- Observed outcome.
- Related files.
- Related commit, when applicable.
- Follow-up decision.

Generate short, sequential implementation prompts.

Do not create one enormous implementation prompt.

Each implementation stage must have explicit acceptance criteria.

---

# 18. IMPLEMENTATION TIME MANAGEMENT

Treat the approximate two-hour implementation budget as a hard constraint until the official assessment establishes otherwise.

Verify which preparation activities are permitted before the timed implementation.

Do not assume that application-specific preparation is automatically exempt.

Separate:

- Allowed preparation.
- Timed implementation.
- Evaluation.
- Submission.

Prioritize a working MVP.

Reserve time for automated testing, evaluation, iteration, and final delivery.

Optional features must not compromise required functionality.

---

# 19. REQUIRED FIRST DELIVERABLE

Consolidate all delegated research into one coherent technical advisory report.

The report must include:

1. Executive summary.
2. Verified assessment requirements.
3. Missing information and ambiguities.
4. Sezzle business and brand analysis.
5. SDD methodology and tooling recommendation.
6. Architecture alternatives.
7. Recommended architecture.
8. RAG and tool-calling strategy.
9. Development-agent responsibilities.
10. Claude Cloud integration feasibility.
11. Gemini paid/free fallback architecture.
12. Skills and MCP recommendations.
13. GitHub workflow and coding standards.
14. Security and confidentiality strategy.
15. Deployment alternatives and 21-day cost estimate.
16. Evaluation strategy.
17. Preparation checklist.
18. Implementation time allocation.
19. Main risks and mitigations.
20. Decisions requiring my approval.

Cite official sources for externally verified technical claims.

Clearly identify unverified assumptions.

Present one coherent recommended strategy rather than multiple contradictory recommendations.

---

# 20. FIRST EXECUTION PROTOCOL

Begin by inventorying the assessment files and inspecting the existing development-agent environment.

Delegate bounded research tasks where useful.

Do not implement the application.

Do not install additional tools.

Do not create or publish a repository.

Do not deploy infrastructure.

Do not expose secrets.

Do not consume cloud credits merely to investigate integration feasibility.

Analyze the materials, research the available options, consolidate findings, and produce the technical advisory report.

End with a prioritized preparation roadmap and the specific decisions requiring my approval.

Wait for explicit authorization before proceeding to implementation.

Your objective is to prepare a reliable, professionally engineered, specification-driven Applied AI assessment that demonstrates sound technical judgment and effective use of AI development agents.
