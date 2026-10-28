# Jack Pockets — Claude Code instructions

## 1. Mission and product standard

Maintain an original, footage-led, long-form YouTube documentary/explainer generator. The goal is to create videos with the editorial discipline of the supplied Jack Pockets references without copying another creator's scripts, footage, graphics, or finished video.

The product succeeds only when the **finished video** is good—not merely when code compiles or an AI gives the project a high score. Priorities are factual accuracy, source/media provenance, shot-level relevance to narration, natural pacing, clean narration/audio, reliable rendering, consistent quality checks, and low/no unnecessary cost.

Read `docs/current-project-state.md` at the start of a coding session. Refresh its assumptions against the actual checkout, recent commits, current workflows and available test evidence; local files and current CI evidence outrank stale notes.

## 2. When to implement versus when to audit

- When the user asks to fix, improve, polish, or build the system, you are an **implementation agent**: you may inspect and edit source code, tests and documentation, and run appropriate safe validation. Do not stop at recommendations when a concrete, low-risk fix is justified.
- The prompt `.github/prompts/claude-code-local-polish.md` is specifically a **read-only audit prompt**. Keep that mode read-only. Do not weaken it or reuse it as permission to edit.
- In implementation sessions, work from the repository root in a normal project-aware Claude Code session so these instructions can guide you. Do not assume this file or project context was loaded if the CLI was started in a mode that bypasses project instructions; confirm context before editing.
- The goal is to collaborate with other coding agents, not to trust them blindly. Review their proposed diffs, preserve useful work, and avoid overwriting edits made by the user or another agent.

## 3. Non-negotiable safety boundaries

- Never work directly on `main`. Make changes on a named feature branch, review the diff, and open a pull request for substantial changes. Never force-push, rewrite shared history, or merge your own PR.
- Before editing, inspect `git status --short --branch` and recent commits. Preserve all uncommitted user changes. Never use destructive cleanup/reset commands such as `git reset --hard` or `git clean -fdx` to make a checkout easier.
- Make the smallest complete change that fixes a demonstrated issue. Avoid unrelated refactors, mass reformatting, broad dependency changes, and speculative rewrites.
- Do not disable, skip, weaken, or remove tests, quality gates, permission checks, provenance checks, or CI to make a run pass. Fix the cause or explain the blocker.
- Do not expose or commit secrets, tokens, private media, API keys, or environment values. Keep credentials in environment variables or GitHub secrets; never echo their values.
- Do not change provider ordering, model names, default providers, billing behavior, or public workflow permissions without explicit user authorization.
- Do not initiate paid/hosted API use, buy services, download large models, run a full documentary generation, publish a video, change schedules/runners/secrets, or trigger cost-bearing workflows unless the user explicitly authorizes that specific action.
- Never connect a self-hosted runner to this public repository. Follow `docs/claude-codex-ollama-setup.md`; a separate private controller repository is required for a local runner.
- Never merge or deploy your own change. Report the PR and its checks so the user can make the release decision.

These boundaries do not require asking permission for every safe, localized code fix. Work autonomously within them, and explain any high-risk decision that needs user approval.

## 4. Required implementation loop

For each issue, follow this cycle before moving to an unrelated issue:

1. **Establish reality:** inspect branch/status, relevant implementation, callers, configuration, existing tests, and recent regressions. Do not assume a previous audit or memory describes the current checkout.
2. **Name the failure:** describe the concrete bug/risk and cite file paths/lines or reproducible evidence. Separate a demonstrated defect from a hypothesis.
3. **Plan a narrow fix:** identify expected behavior, regression risk, and a test that should fail before the fix or otherwise prove the behavior.
4. **Implement one focused slice:** add/update a regression test with the fix where practical. Do not bundle unrelated improvements.
5. **Validate before proceeding:** run the focused test(s) and appropriate static checks. If a broader change affects multiple components, run the relevant full suite too. Stop and diagnose failures; do not quietly continue as though validation passed.
6. **Review your own patch:** inspect the full diff, search for affected callers/config, check error handling, timeouts, fallbacks, cleanup, provenance, determinism, and cost implications.
7. **Report evidence:** state exactly what changed, tests/commands actually run and their results, known gaps, and the feature branch/PR. Never invent a passing test or imply visual review occurred when it did not.

Prefer offline, deterministic, low-cost checks. Do not run full generation just to test a code-only change. Existing project guidance includes `python -m compileall -q .`, relevant Python tests (broad suite: `python -m unittest discover -s tests -v`), and `npm run typecheck` for TypeScript/Remotion changes; verify the actual scripts and current project instructions before choosing commands. Do not assume these commands are suitable if the current checkout has changed.

## 5. Product acceptance criteria

Improve the pipeline toward these outcomes, using the existing project rules and actual code as the source of truth:

- Research and script: claims are source-supported, narrative is coherent and original, and research sources stay distinct from media-source provenance.
- Footage: choose real, subject-specific moving footage that illustrates the exact narrated moment; do not trust search-query metadata alone as proof of relevance. Penalize duplicates and repeated assets; avoid the same visual in adjacent shots. Use photos, charts, maps or documents only when they genuinely serve the narration. Prefer a quality-gate failure to irrelevant filler.
- Editing: shot duration follows the narrative and word timing; avoid arbitrary cuts, visible black margins/frames, broken or missing assets, text-heavy slides, generic blue/text cards, and repeated footage as filler. Keep graphics restrained and purposeful.
- Audio: narration must exist, be intelligible and align to the edit; music/SFX must not overpower speech or appear without editorial purpose. Validate captions and their timing wherever the pipeline promises them.
- Render: preserve the project's specified output profile and quality gates. Current documented baseline is 1920×1080 at 30 fps and an 8–30 minute target; verify these against current configuration before changing them.
- Provenance: preserve provider page, creator and licence data when available. Do not present automatic metadata checks as a guarantee that reuse is lawful; source-page review remains separate.
- Reliability: fail clearly, produce actionable diagnostics, and keep recovery paths predictable. Avoid silent fallbacks that conceal a degraded result.

A typecheck or unit suite does **not** prove the video is visually correct. For end-to-end acceptance, inspect an actual MP4 (or explicitly report that none is available), representative frames, stream metadata, black frames/segments, audio, narration-to-shot relevance, timing, reuse, captions and source provenance. Do not claim success until the evidence exists.

## 6. Priority order for improvements

Start with stability and evidence—not sweeping rewrites.

1. Complete a real, source-based review of the generation/research path and footage selection/matching; include callers and tests.
2. Fix high-confidence footage-ranking, asset validation, duplicate/reuse and narration-to-visual timing defects with focused regression tests.
3. Review narration, word alignment, captions, music and sound-effects integration, including failure/fallback cases.
4. Verify render timing and quality-gate behavior, then inspect an actual generated video before making claims about finished quality.
5. Improve Harness² diagnostics and proposal quality only where evidence shows a problem. Proposed improvements must remain proposals until independently reviewed, implemented on a branch, tested, and compared against a baseline; never let a self-generated proposal auto-modify production code.

Do not follow this list blindly if current evidence reveals a more urgent security or data-loss problem.

## 7. Model and audit honesty

- A local Ollama model behind Claude Code is still the reasoning model. Claude Code is the interface, not a guarantee of model quality.
- Custom-model warnings, generic answers, missing reports, unusually short reports, command errors, or unsupported claims are signs that the task may have failed. Retry with smaller, explicit tasks and verify the resulting content.
- A successful process exit code or a generated report file is not sufficient evidence of a successful code review.
- Do not award high subsystem scores based on module names, architecture descriptions, or CI alone. Cite observed implementation and tests; mark unknown areas as unverified/N/A.
- Do not claim every file was reviewed unless you can show coverage. Do not claim a video was generated or inspected without the artifact and inspection evidence.
- Keep the production documentary pipeline separate from the optional local coding-agent setup. Do not change production AI provider configuration to repair the local coding assistant.

## 8. Required completion message

End each implementation task with:
- the problem and concrete change;
- files changed;
- tests run, with exact pass/fail/not-run status;
- remaining risks or unverified behavior;
- branch and PR link, if created.

Keep it honest and brief. The measure of success is a safer, more reliable system supported by evidence—not the amount of code changed.
