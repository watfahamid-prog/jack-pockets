# Jack Pockets — current project state

**State note date:** 2026-10-28

This is a snapshot, not a substitute for checking the actual repository, tests, live CI, and available media artifacts.

## Product goal

Build an original, footage-led long-form documentary generator. The intended flow is:

Topic → research → story plan → narration → word alignment → media search → sentence-level visual selection → restrained graphics/SFX → quality gate → Remotion render → MP4 validation.

The quality target is a polished YouTube documentary/explainer, not a ranking-style Short or a slideshow. Real, topic-specific moving footage should carry the story; graphics should explain evidence only when useful. Do not copy another creator's script, footage, graphics, or finished video.

## Repository shape

The project combines Python orchestration, research/media/audio/QC components, TypeScript/Remotion rendering, FFmpeg/FFprobe, regression tests, GitHub Actions, and Harness² run recording/proposals.

Key areas include:
- research, script generation, and editorial planning;
- asset discovery, relevance/ranking, validation, and provenance;
- narration/TTS, word alignment, captions, music, and SFX;
- Remotion composition, FFmpeg rendering, manifest/configuration, and video QC;
- regression tests, CI, generation evidence, and improvement proposals.

## Evidence limits

Passing CI, syntax checks, and typechecks do not prove that a finished documentary is good. A quality claim requires an actual MP4 and inspection of representative frames, audio, narration-to-footage relevance, captions, pacing, and diagnostics. Do not describe a video as visually verified unless that inspection actually occurred.

Documentary generation is manual-only unless the repository owner explicitly approves a run. Hosted model/media provider use may incur costs depending on configured credentials and services.

## Safe next steps

1. Verify the current branch, commit, working-tree status, and latest CI before making changes.
2. Inspect the implementation and regression tests for one specific problem at a time.
3. Run focused tests first and record exact commands and outcomes.
4. Preserve source provenance, footage relevance checks, quality gates, and all existing user work.
5. When a real MP4 is available and inspection is authorized, review resolution/FPS/duration, representative frames, black segments/margins, audio, narration-to-shot alignment, repetition, captions, and provenance.
6. Update this note only when newer evidence exists. Distinguish tested facts from assumptions.
