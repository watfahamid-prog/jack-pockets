# Jack Pockets Engineering Review Ledger

**Review status:** In progress; targeted fixes are under review in draft PR #96.  
**Baseline:** `96f2336e04e3071b233ff1958c5f3ca245b23d34` on `main`.  
**Scope:** Reliability pass, not a claim that the whole system is “100 times better.” No generation run or finished MP4 inspection was performed.

## Review intent

Improve the reliability of an original, evidence-led, footage-first long-form documentary pipeline without weakening existing quality thresholds, contacting paid providers during code review, running full documentary generation, or merging unreviewed changes.

## Areas inspected

- Generation orchestration and ordering in `generate.py`.
- Research provider fallback/caching in `research.py`; plan normalization and provider selection in `llm.py`.
- Source relevance and authority shortlisting in `relevance.py`.
- Footage provider selection, local downloads, attribution, and license checks in `assets.py`.
- Sentence-to-asset selection and word-span matching in `editorial_brain.py`.
- Manifest timing and beat/shot assembly in `manifest.py`.
- Source provenance, clip existence, coverage, repetition, and movement constraints in `quality.py`.
- FFprobe/FFmpeg/optional scene diagnostics in `video_qc.py`.
- Remotion shot timing and overlays in `JackPocketsVideo.tsx`; caption phrase selection in `caption-utils.js`.
- Narration provider/cache configuration in `tts.py`, alignment backends in `audio_aligner.py`, soundtrack sourcing and download limits in `music.py`, and JSON caching in `cache_utils.py`.
- Manual generation workflow input handling in `.github/workflows/generate-video.yml`.
- Harness² run ledger and proposal utilities under `harness2/`.
- Related regression tests for relevance, manifest/timeline, quality gates, media license policy, QC, source handling, workflow input safety, captions, and Harness².

This is not yet an exhaustive review of every file, all provider behavior, or a real rendered episode.

## Findings addressed in the draft

1. **False-success risk in Harness²:** a `FINAL QC PASSED` log string alone no longer makes a run verified. The recorder requires the claimed MP4 and matching `video-qc.json` identity/technical metadata; it preserves structured warnings and differentiates `passed_with_warnings`.
2. **Diagnostic failures could look clean:** failed black-frame scans and failed optional scene-change analysis now generate explicit warnings.
3. **Narration/shot alignment:** apostrophe normalization improves contraction matching. The manifest keeps a shot visible over leading and inter-beat pauses instead of leaving no active beat, and each selected Remotion shot has a finite sequence.
4. **Source graphics and citations:** source/document graphics now consume only the URLs selected by the per-beat relevance/authority shortlist. Raw search data remains in `research.json` for auditability; manifest citations are sourced from selected beat URLs.
5. **Media reuse policy:** Archive and Wikimedia Commons selection conservatively rejects NC/ND/SA and unknown licenses; CC BY requires creator attribution. Metadata whitespace is normalized, with a mocked Commons-provider test ensuring restricted items are rejected before download.
6. **Evidence gate timing:** missing or invalid per-beat citation URLs now fail before narration synthesis and media acquisition, instead of only failing after expensive pipeline work.
7. **File and workflow safety:** the quality gate rejects missing local assets and paths escaping `public`; the manual topic input uses a random delimiter when writing to `GITHUB_ENV`; citation URLs must use HTTP(S).

These checks are guardrails. A heuristic relevance shortlist is not proof that a source independently supports every factual claim.

## Validation evidence

The code head `a7e425548ccddae55155efd5bc0a9f46f7bbc739` passed all seven GitHub Actions workflows after fixing a regression-test fixture:
- Pipeline regression tests.
- Validate documentary pipeline.
- Typecheck and Python syntax.
- Footage Matching Tests.
- TTS fallback tests.
- Validate GitHub Actions workflows.
- Harness² Free Demo (Isolated).

The complete Python regression suite and Remotion typecheck passed on that head. A documentation-only ledger commit may rerun CI; the checks tab for the current PR head remains authoritative.

A previous CI failure was traced to a test fixture that encoded the literal characters `\\n` instead of an actual newline. The fixture was corrected, and the subsequent seven-workflow run passed.

## Not yet proven

- No new documentary MP4 was generated or inspected. Therefore clip relevance against narration, pacing, visual variety, caption appearance, audio loudness/balance, and the overall viewing experience remain unverified.
- The research relevance score uses metadata/token overlap; it does not independently fact-check claims.
- The full subsystem-by-subsystem inventory and all remaining edge cases are not complete.
- The separate TTS cache-invalidation PR #95 has not been merged by this work.
- Changes remain in draft PR #96 and are not merged to `main`.

## Next highest-priority steps

1. Continue the code audit, especially how every factual statement maps to supporting source evidence and how selected media is verified before final render.
2. Add deterministic tests around pipeline ordering, failure recovery, and source/asset provenance without contacting real providers.
3. When a run is explicitly authorized and its providers/cost are understood, inspect an actual MP4, frames, audio, captions, manifest, and QC report before making visual-quality claims.
4. Update this ledger with only verified findings and test evidence. Keep quality gates intact; do not weaken them merely to force a successful render.
