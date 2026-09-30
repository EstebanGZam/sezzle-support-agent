# P-010 — Final documentation and submission review request (verbatim, user → lead)

- Category: Planning prompt

---

I need you to perform a final documentation and submission review of the assessment.

Do not change the application architecture or core behavior unless you discover a clear documentation inconsistency that must be corrected.

Your goal is to make the final submission easy for a reviewer to understand, execute, inspect, and evaluate.

## 1. README as the main navigation document

Review the current README.md and make it the main entry point for the entire assessment.

From the README, the reviewer should be able to easily find every artifact required by the assessment.

The README should clearly link to or reference, where applicable:

- The implementation.
- run_cases.py.
- DECISIONS.md.
- PROMPTS.md.
- ITERATION.md or equivalent evaluation/iteration evidence.
- Evaluation results.
- Specifications.
- Assumptions.
- Architecture documentation.
- Security documentation.
- Any required prompt logs.
- Any other artifact explicitly requested by PROMPT.md or SUBMISSION.md.

Do not duplicate large amounts of documentation inside README.md.

Use README.md as a concise navigation and execution guide.

Verify against the original assessment documents that every required deliverable is represented and easy to locate.

## 2. Instructions to run and test the system

The README must contain clear, reproducible instructions for testing the project from a clean environment.

Include:

- Required Python version.
- Dependency installation.
- Environment variable setup.
- How to configure the LLM API key safely.
- The exact command required by the assessment:
  python3 run_cases.py <cases.jsonl> <answers.jsonl>
- How to run the provided visible/golden cases.
- How to inspect the generated answers.
- How to run unit tests.
- How to run the evaluation/scoring tools, if applicable.
- Any relevant lint or quality commands.
- Expected high-level behavior.
- Known limitations or provider-related caveats.

The instructions must be sufficient for a reviewer who has never seen my local environment.

Do not depend on Orchestrator, Claude Code, Codex, tmux, my local paths, or any other development-only tooling.

The submitted project must be independently executable.

## 3. Future work / unfinished work

The assessment requests that I explain what I would do with more time.

Create or update an appropriate concise section in README.md describing the main future improvements I would propose.

The two main future improvements should be:

### Production deployment

Prepare the assistant for a real production environment.

This could include, where appropriate:

- Production hosting.
- Secure secret management.
- Authentication and authorization.
- Rate limiting.
- Monitoring and observability.
- Production-grade logging.
- Reliability and scaling.
- Concurrency.
- Cost controls.
- CI/CD.
- Provider resilience.
- Security hardening.

Do not claim these features were implemented if they were not.

### Web user interface

Add a lightweight web interface so the assistant can be used interactively instead of only through the CLI assessment contract.

The future architecture should preserve the existing support-agent core and expose it through a thin web/API layer.

A possible future direction may include a web UI and an API adapter such as FastAPI, but describe this as future work rather than implemented functionality unless it already exists.

The CLI contract required by Sezzle must remain supported.

Keep this section practical and concise.

## 4. Traceability of assessment results

Verify whether the first evaluation run, subsequent iteration, and final results are already stored and documented.

Confirm that the reviewer can find:

- Initial/baseline results.
- Observed failures.
- Failure taxonomy, if required.
- What was changed.
- Why it was changed.
- Final evaluation results.
- Any relevant latency, cost, or provider measurements that were actually observed.

Do not invent missing measurements.

If any required result exists but is difficult to discover, improve the README references.

If anything required by the assessment is genuinely missing, report it to me before fabricating or reconstructing evidence.

## 5. Prompt traceability

Verify that the important prompts used to develop the assessment are documented in the required location.

Ensure that PROMPTS.md or the relevant prompt documentation is easy to discover from README.md.

Do not delete meaningful prompt evidence merely because development occurred across multiple days.

However, review the final submission for unnecessary timestamps, internal scheduling details, or development chronology that the assessment does not require. If any logs contain timestamps, remove them unless the assessment explicitly requires them.

If exact execution dates or times are not required by the assessment, do not emphasize them in the final reviewer-facing documentation.

Preserve the actual prompt content.

## 6. Time statement

I personally tracked approximately 2 hours and 15 minutes of focused assessment work.

Do not create detailed timing logs or reconstruct timestamps unless explicitly required by the official assessment.

The only time-related statement that should be included is: "I tracked my time independently and spent approximately 2 hours and 15 minutes in total." If the assessment expects a time statement, include only a concise and honest note such as:

"Focused implementation and evaluation time: approximately 2h 15m (tracked independently)."

Only include this if it is appropriate according to PROMPT.md and SUBMISSION.md.

Do not overemphasize the fact that the repository was worked on across multiple calendar days.

Do not remove factual development records that are required for traceability.

## 7. Final ZIP / submission contents

Review PROMPT.md and SUBMISSION.md and tell me exactly what should be included in the final submission ZIP.

Prepare a submission manifest.

Classify files into:

- REQUIRED — explicitly required by the assessment.
- RECOMMENDED — useful for reproducibility or review.
- EXCLUDE — local-only, sensitive, unnecessary, or development-only.

Verify whether the final ZIP should contain items such as:

- Source code.
- run_cases.py.
- Policy documents.
- Mock order data.
- Visible cases.
- Tests.
- Evaluation tools.
- First and final evaluation artifacts.
- README.md.
- DECISIONS.md.
- PROMPTS.md.
- ITERATION.md.
- Dependency files.
- .env.example.
- Specifications.
- Architecture/security documentation.

Explicitly exclude:

- .env.
- API keys.
- credentials.
- local caches.
- virtual environments.
- IDE files.
- temporary files.
- agent worktrees.
- hidden holdout cases unless the assessment explicitly requires them.
- internal files that do not belong in the reviewer submission.

Do not assume. Base the final manifest on the actual assessment instructions.

## 8. Final submission validation

Before considering this task complete, verify:

- The required CLI command works from the final repository structure.
- No secrets are present.
- README links/references are correct.
- Required deliverables are present.
- The ZIP can be created cleanly.
- A reviewer can reproduce the project without my development tools.
- The submission does not depend on a deployed service.
- Any unfinished features are clearly labeled.
- The future production deployment and web UI are described as future work, not implemented features.

## 9. Deliverables for me

At the end, provide me with:

1. The updated README.md.
2. A checklist mapping every Sezzle requirement to the final file that satisfies it.
3. The exact proposed ZIP contents.
4. The exact files/directories that should be excluded.
5. Any remaining submission blocker.
6. The exact command I should use to create the final ZIP.

Do not publish anything or create a remote repository.

Do not deploy anything.

Do not delete evidence without first identifying why it should be removed.

Communicate the final summary to me in Spanish. Keep all repository documentation in English.
