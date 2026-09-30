# P-003 — Technology stack comparison prompt (verbatim, user → lead)

- Tool/agent: Claude Code (lead orchestrator, Opus 5.5)
- Category: Planning prompt

---

I have reviewed your advisory report and would like to clarify our decision-making process. You are my technical research and advisory team.

Your responsibility is to investigate, compare, challenge assumptions, and recommend. I retain final authority over technology selection, architectural decisions, and implementation approval.

Do not independently approve or lock the technology stack.

## Objective

Using the actual assessment documents and your completed research, prepare a concise, evidence-based technical stack comparison that enables me to make the final engineering decisions.

Do not repeat the entire advisory report.

Focus on the decisions that materially affect the solution.

## Areas to evaluate

1. Repository structure and organization of the original assessment materials.
2. Application language and framework, including Python, FastAPI, Spring Boot, and relevant alternatives.
3. LLM orchestration and tool calling.
4. Policy grounding, complete-context retrieval, lightweight RAG, or other appropriate approaches.
5. Shared knowledge resources, concurrency, and independent user sessions.
6. Data validation, authorization, and application-level security.
7. Gemini integration, configuration, and provider portability.
8. Automated testing, LLM evaluation, and observability.
9. Dependency management, CI, and deployment.
10. Integration with our existing Orchestrator, Claude Code, Codex, and development tools.

For each major decision, explain:

- Available options.
- Relevant assessment requirements.
- Advantages and disadvantages.
- Complexity and operational implications.
- Security and maintainability considerations.
- Estimated implementation effort.
- Your recommended option and why.
- Circumstances under which another option would be preferable.

Do not introduce technologies merely to demonstrate sophistication.

## Security and architectural expectations

The solution should be designed for its explicit customer-support purpose.

Investigate appropriate safeguards for domain restriction, prompt injection, unauthorized access, excessive inference consumption, user isolation, concurrent execution, and safe failure behavior.

Prefer structural controls enforced by application code rather than relying exclusively on LLM instructions.

Consider efficient reuse of shared policy resources across sessions.

Balance production-oriented design with the actual assessment scope.

## Decision ownership

Separate clearly:

- Explicit requirements from Sezzle.
- Your technical recommendations.
- Assumptions.
- Decisions requiring my approval.

Do not convert recommendations into approved requirements.

Do not create or modify application code.

Do not begin implementation.

## Documentation

Preserve this prompt and your research results in the project prompt log.

Prepare an architectural decision matrix for my review.

All technical artifacts must be written in English. Explain your findings to me in Spanish.

End with a concise list of the technology decisions I must make before you prepare the implementation specifications.
