# Jack Pockets — current project state

**State note date:** 2026-10-28  
**Purpose:** Give Claude Code a grounded starting point. This is a snapshot, not a substitute for checking the actual checkout.

## Product goal

Build an original, footage-led long-form documentary generator. The intended flow is:

Topic → research → story plan → narration → word alignment → media search → sentence-level visual selection → restrained graphics/SFX → quality gate → Remotion render → MP4 validation.

The quality target is a polished YouTube documentary/explainer, not a ranking-style Short or a slideshow. Real, topic-specific moving footage should carry the story; graphics should explain evidence only when useful. Do not copy another creator's script, footage, graphics or finished video.

## Repository shape

The project combines Python orchestration/research/media/audio/QC components with TypeScript/Remotion rendering and FFmpeg/FFprobe. Read `README.md`, `AGENTS.md`, `CLAUDE.md`, current workflows, and the actual callers/tests before modifying anything. Verify actual filenames and package scripts rather than relying on this note.

Key documented areas include:
- research, script generation and editorial planning;
- asset discovery, relevance/ranking, validation and provenance;
- narration/TTS, word alignment, captions, music and SFX;
- Remotion composition, FFmpeg rendering, manifest/configuration and video QC;
- regression tests, GitHub Actions and Harness² run recording/proposals.

## Last known validation evidence

The latest status reported for the main baseline on 2026-10-27 was commit `e0d29f6f84ed72685d6286d3252c6b6a9f91a9c3`. The following GitHub Actions runs were reported passing at that point:

- [Validate documentary pipeline](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40532702461)
- [Pipeline regression tests](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40532702517)
- [Typecheck and Python syntax](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40532702669)
- [Validate GitHub Actions workflows](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40532702938)

These results support the checks listed in those runs only. They do not prove end-to-end video quality, real-footage relevance, narration synchronization, or visual/audio correctness. Always check live status and current commit before using these as evidence.

## Current blockers and limitations

1. **A fully verified output video has not been established by the evidence in this note.** Do not claim Jack Pockets already produces reference-level results until an actual MP4 and its frames/audio are inspected.
2. The six-part local Claude/Ollama audit attempted on 2026-10-28 was incomplete:
   - architecture/research report was only about 102 bytes;
   - footage-matching report was only about 164 bytes;
   - audio/captions/music report was only about 674 bytes;
   - rendering, tests/security and Harness² reports were longer, but their findings still require source-based verification.
3. The integration summary returned a **PARTIAL** verdict but assigned an overall **5.5/10** score despite missing evidence. Treat that number and subsystem scores as **unverified**, not as an established rating of the code.
4. The local model produced the warning `unrecognized_model` for `jack-pockets-audit:16k`, and some attempts failed from output limits or incorrect file access. A report file and exit code 0 are not proof of a reliable audit.
5. The public repository's local Claude audit workflow is manual-only and read-only. The documented private-controller setup for local scheduled execution is not evidence that a daily runner is already operational.

## Security and operating mode

- This public repository must not run untrusted pull-request code on a laptop-hosted self-hosted runner. Follow `docs/claude-codex-ollama-setup.md`; use a separate private controller repository for any private local-runner workflow.
- Documentary generation is manual-only until actual output quality is satisfactory. Do not enable schedules or run cost-bearing API calls without explicit approval.
- The local code agent is expected to help implement scoped improvements in feature branches, with regression tests and evidence. The separate read-only audit prompt stays read-only.
- Never push directly to `main`, discard user changes, disable quality gates, or auto-merge agent-written code.

## Recommended next work

1. Verify the actual current branch/commit and working-tree status; preserve any local edits.
2. Read the implementation and tests for research/orchestration and footage selection/ranking. Complete these audits properly; do not trust the failed reports above.
3. Inspect audio/TTS, word alignment, caption timing, music and SFX paths, including fallback/error behavior.
4. Run the relevant low-cost tests and current CI checks.
5. When a real MP4 is already available or generation is explicitly approved, inspect duration/FPS/resolution, representative frames, black segments/margins, audio, shot relevance versus narration, reuse, captions and provenance.
6. Update this status note only when newer evidence exists. Record the evidence and date; never change “unverified” to “passed” based on code review alone.
