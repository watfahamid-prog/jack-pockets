# Jack Pockets AI coding team workflow

## Purpose

Use ChatGPT as the manager and final evidence reviewer, Codex Desktop as the primary implementation agent, and Claude Code as an independent reviewer when it can be used with existing access and without unexpected cost. Coordinate through GitHub branches, pull requests, test evidence, and the repository's instructions—not assumptions that the agents can read each other's private chat histories.

This is a working agreement, not a claim that the desktop apps are already directly connected or that automation has been activated.

## Roles

### ChatGPT — manager and final reviewer

- Identify a concrete failure or improvement from current source, CI, logs, or video evidence.
- Define one bounded task, expected behavior, acceptance criteria, cost limits, and test plan.
- Use the connected GitHub repository to inspect branches, diffs, issue history, and CI results; record durable findings in the relevant PR or project-state document.
- Independently review Codex and Claude findings against source and evidence. Challenge unsupported claims and reject changes that pass tests but do not meet product requirements.
- Do not say a desktop app was controlled, a command was run, a video was inspected, or a test passed unless there is actual evidence.

### Codex Desktop — primary implementation agent

- Open the local Jack Pockets Git repository in ChatGPT Desktop's Codex view.
- For code changes, prefer Codex's **Worktree** mode so the task is isolated from the user's main checkout. Never implement directly on main.
- Read AGENTS.md, README.md, docs/current-project-state.md, and relevant tests before changing code.
- Implement only the assigned task, write/update regression tests, run relevant checks, inspect its complete diff, then present a branch or PR for review. Do not merge.
- Do not switch to the Codex CLI bridge for automation unless the user explicitly reauthorizes it. The local bridge is currently not activated; the user reported poor results from CLI testing.

### Claude Code — independent, read-only reviewer by default

- Review Codex's proposed PR after the implementation is available. Use a separate worktree or checkout at the PR head; do not edit the same worktree concurrently with Codex.
- Start in read-only review mode: inspect the full diff and relevant callers/tests; look for correctness, regressions, security/data-loss risks, edge cases, test gaps, and impact on real video output.
- Report actionable findings with severity, exact file/line, evidence, and a suggested correction. Mark speculative concerns as hypotheses.
- Do not rewrite the implementation or change files during an independent review. If the user explicitly delegates implementation to Claude, use a separate branch/worktree and submit a separate PR.
- Use Claude Code only through an existing authorized sign-in/access path. Do not install it, enable a paid GitHub review service, use an API key, purchase credits, or trigger paid usage without the user's explicit approval. If access is unavailable or the cost is unclear, mark this review step as not run.

## Task lifecycle

1. **Manager defines the task.** One problem at a time, grounded in source/CI/artifact evidence. State expected behavior, non-goals, regression tests, and any cost boundaries in a GitHub issue or PR description.
2. **Codex implements in isolation.** Start from current main in Codex Desktop Worktree mode. Avoid touching unrelated files and never weaken quality gates.
3. **Codex reports evidence.** Record changed files, commands actually run, exact pass/fail results, branch/commit or PR, and remaining risks. Separate local test evidence from GitHub CI.
4. **Claude independently reviews.** Review the proposed diff in a separate checkout/worktree. Return findings without modifying Codex's files. Skip honestly if Claude Code access is not available without added cost.
5. **Codex fixes verified findings.** Keep fixes on the implementation branch where safe; rerun the relevant tests and any checks affected by the changes. If the review reveals a major scope change, pause and split the task.
6. **ChatGPT performs final review.** Inspect the actual diff, CI checks and review findings via GitHub. Request corrections if needed. A human/repository owner retains the merge decision; do not auto-merge agent-authored changes.
7. **Update shared handoff.** Record material discoveries and remaining work in the PR and, when useful, docs/current-project-state.md. Never commit private chat logs, credentials, or local environment details.

## Required quality gates

- A focused regression test should prove the bug or expected behavior; run relevant broader tests and typecheck/syntax checks according to AGENTS.md.
- Never claim tests passed when only a command was suggested or started. Record failures and diagnose them before moving on.
- For any change that may affect finished video: CI is necessary but not sufficient. Inspect an actual MP4 and representative frames/audio, timing, black frames/margins, caption alignment, shot-to-narration relevance, duplicate visuals and provenance when an artifact can be produced safely without unauthorized cost. If no video was generated or inspected, say so explicitly.
- Do not run full documentary generation, make paid API calls, download large models/assets, publish media, or alter provider/billing policy without explicit approval.
- Prefer one well-evidenced fix over several speculative changes or extra agents that add complexity without measurable improvement.

## Handoff prompts

### Codex Desktop implementation prompt

“Work as the primary implementation agent for this single Jack Pockets task. Read AGENTS.md, README.md, docs/current-project-state.md, and the relevant implementation/tests. Work in a Codex Desktop Worktree, never directly on main. Reproduce or demonstrate the problem first, make the smallest complete fix, add/update a regression test, run the focused tests and applicable static checks, inspect the complete diff, and report exact commands/results and risks. Do not run full video generation, paid APIs, large downloads, change billing/provider behavior, or merge. Do not claim any test or video inspection you did not actually perform. Task/PR: [link].”

### Claude Code independent review prompt

“Review this Codex-authored Jack Pockets PR independently and read-only. Read AGENTS.md, CLAUDE.md, README.md, docs/current-project-state.md, the full PR diff, affected callers and tests. Do not modify files. Look for proven bugs, regressions, edge cases, security/data-loss risks, missing tests, and impact on actual video quality. For each finding, report severity, file/line, supporting evidence, and a concrete fix. Verify rather than infer; label uncertainty. Also report what you could not test and whether your review used any billable access. PR: [link].”

## Connection and cost boundaries

The desktop products have separate controls and histories. Use a supported Quick Chat handoff in Codex Desktop when it is available to bring this ChatGPT conversation into context; otherwise use this document and a GitHub issue/PR as the durable handoff. This does not make the applications silently share every message or authorize one app to control another.

Default setup is manual desktop Codex plus GitHub-mediated review. Do not install or activate the local Codex CLI bridge for this team without explicit reauthorization. Do not enable Claude's hosted GitHub Code Review or any paid automation by default. GitHub checks, this ChatGPT-to-GitHub connection, and Codex Desktop's own Worktree feature are separate capabilities; verify each before claiming it is active.

## What counts as a successful team

Success is measured by confirmed defect fixes, passing relevant tests, honest independent review, fewer regressions, and better inspected video output—not by the number of agents, the volume of edits, or self-assigned scores.
