# Jack Pockets repository-wide audit

**Audit date:** 2026-10-24  
**Audited baseline:** `main` after workflow-only PR #62; production code is unchanged from `89e2d44` (PR #60).  
**Method:** static source/config review plus GitHub Actions run/job/log evidence. This is not a claim that a fresh documentary MP4 was visually reviewed: no newly generated MP4 was available to inspect during this audit.

## Executive summary

The repository has a substantial pipeline and useful guardrails: 26 test-related files/scripts, 11 GitHub Actions workflows, Python compilation, a Python unittest suite, Remotion typechecking, a manifest quality gate, per-file media download limits, source-authority ranking, and FFprobe checks for the final MP4.

The most important remaining gaps are at the boundaries between components: selecting Qwen does not reliably prevent Gemini editor API calls; caption visibility is keyed to each individual word interval; and the final video QC that can detect long black segments/scene changes is optional and disabled by default. Metadata-based relevance checks help, but cannot prove that the actual downloaded frames match the narration. The final artifact still needs an explicit visual/audio inspection.

## 1. Repository map

### Main video pipeline

1. **Entry point/orchestration — `generate.py`**: accepts topic/profile/asset count; searches topic and beat research; generates the plan; creates narration; aligns words; searches assets; builds a manifest; creates SFX/music; runs the manifest quality gate; renders with Remotion; validates MP4 streams, dimensions, FPS and duration.
2. **Research — `research.py`**: Perplexity Search first, Tavily fallback, Wikipedia background, and Europe PMC for science queries or when results are sparse. `cache_utils.py` caches successful results. `relevance.py` ranks supporting sources using topical matches and an authority score.
3. **Story plan / AI providers — `llm.py`, `generate_script.py`, `qwen_smoke_test.py`**: the default `auto` order is Gemini → OpenAI → Anthropic; Qwen through an OpenAI-compatible endpoint is opt-in. The plan normalizer enforces beat count, narration length, keywords and duplicate-sentence limits.
4. **Narration — `tts.py`**: ElevenLabs/OpenAI TTS where configured, Edge TTS and Piper fallbacks, and explicit local Kokoro/Piper options. `requirements-kokoro.txt` and the provider setting gate optional local narration.
5. **Word alignment — `audio_aligner.py`**: Faster-Whisper by default, optional WhisperX; emits word-level timestamps used by the manifest and captions.
6. **Footage and explanatory visuals — `assets.py`, `relevance.py`, `semantic_ranker.py`, `editorial_brain.py`**: Pexels, Pixabay, Wikimedia Commons and Internet Archive search/download paths; relevance filtering; optional local semantic reranking; sentence-level shot selection and reuse penalties. `generate_role_asset` produces selected explanatory graphics.
7. **Editing and manifest — `manifest.py`, `gemini_editor.py`, `quality.py`**: aligns beat timing, optionally refines beats through Gemini, plans shots/layers, and rejects manifests that violate evidence, motion, repetition, timing and asset-reference rules.
8. **Music/SFX — `music.py`, `sfx.py`**: user-authorized direct music URL, eligible Internet Archive music, or a locally generated ambient bed; procedural SFX are generated locally.
9. **Rendering and QC — `Root.tsx`, `index.tsx`, `JackPocketsVideo.tsx`, `types.ts`, `config.ts`**: Remotion composition renders 1920×1080 at 30 fps with audio, shot layers, motion, captions and optional progress bar. `generate.py` runs mandatory FFprobe checks. `video_qc.py` provides optional black-frame and scene-change diagnostics.
10. **Run learning — `harness2/`**: `record_run.py` records objective run evidence, `propose_improvements.py` creates proposals, `render_native_harness.py` renders a local report, and `validate_harness.py` validates harness data. The generation workflow uploads its learning outputs; this is feedback/proposal machinery, not proof that proposals are automatically safe to merge.

### Dependencies, providers and external engines

- **Node:** Remotion/React/TypeScript packages in `package.json` and `package-lock.json`.
- **Python core:** OpenAI, Anthropic, Google GenAI, requests, python-dotenv, Edge TTS, Piper TTS, Faster-Whisper; FFmpeg/FFprobe are external runtime tools.
- **Optional:** Qwen via local Ollama (`requirements-qwen.txt`); WhisperX (`requirements-whisperx.txt`); Kokoro (`requirements-kokoro.txt`); scene detection (`requirements-scene-qc.txt`); local semantic ranking (`requirements-semantic-ranking.txt`); Harness² dependencies (`requirements-harness2.txt`).
- **Research APIs/sites:** Perplexity, Tavily, Wikipedia, Europe PMC/PubMed/DOI.
- **Media:** Pexels, Pixabay, Wikimedia Commons, Internet Archive.
- **Speech:** Gemini/OpenAI/Anthropic for planning, Gemini editor, ElevenLabs/OpenAI TTS, Edge TTS, Piper, Kokoro, Faster-Whisper/WhisperX, and Ollama/Qwen.
- **Workflows (11):** `footage-tests.yml`, `generate-video.yml`, `harness2-free-demo.yml`, `pipeline-tests.yml`, `qwen-opencode-repair.yml`, `test-commit-logging.yml`, `test-debugging-failure.yml`, `tts-fallback-tests.yml`, `typecheck.yml`, `validate.yml`, `verify-qwen-opencode.yml`.

## 2. Prioritized findings

### P1 — Qwen selection can still trigger Gemini editor API calls

**Evidence:** `manifest.py` calls `refine_beat(beat)` during manifest construction. `gemini_editor.py` returns early only when `GEMINI_API_KEY` is absent; it does not check `LLM_PROVIDER`. The production generation workflow supplies `GEMINI_API_KEY` independently of the selected planner provider. Meanwhile, `QWEN.md` says selecting `LLM_PROVIDER=qwen` uses only Qwen and does not silently fall back to a paid provider.

**Impact:** a run configured for local/free Qwen can still make one Gemini editor request per beat when the Gemini secret is present. This is a cost and provider-selection correctness issue.

**Fix:** make editor-provider selection explicit. For the first safe fix, skip Gemini refinement whenever `LLM_PROVIDER=qwen` unless a separate explicit setting opts in. Add a regression test that proves the Google GenAI client is not called for a Qwen-only run.

**Confidence:** high; direct call path is present in the current source.

### P1 — Captions can disappear between word timestamps

**Evidence:** `JackPocketsVideo.tsx:65-88`. `captionAt` returns a caption only when the current frame falls inside a single word's `start <= time < end` interval; if the frame falls in the gap between adjacent Whisper word intervals, it returns an empty string. `manifest.py` sets `showCaptions: true`, so the caption renderer is enabled, but the per-word gate can still make the line flicker/disappear during natural inter-word gaps. The current test inventory does not include a caption-timing test for this React component.

**Fix:** compute caption phrase windows from grouped words, with a short gap tolerance, rather than requiring the frame to be inside one word interval. Add tests for normal inter-word gaps, pauses, punctuation and the first/last word.

**Confidence:** high for the gap behavior; whether it caused a particular previously observed render needs a real artifact.

### P1 — Visual QC is optional and not enabled in the generation workflow

**Evidence:** `env.example:43` sets `JACKPOCKETS_VIDEO_QC=0`; `generate.py:383-397` only calls `video_qc.inspect_video` when the flag is enabled, and catches diagnostic exceptions without failing the render. `video_qc.py:40-93` can detect black segments and scene cuts, but the `generate-video.yml` render step does not set `JACKPOCKETS_VIDEO_QC`. Mandatory FFprobe checks do verify streams, dimensions, frame rate and duration, but they do not prove that shots are visually relevant or free of unwanted black gaps.

**Fix:** run the diagnostic report on every generated MP4 and upload it; decide explicitly which warnings should fail a run, while allowing intentional fades. Add sampled-frame/contact-sheet review and a narration-to-shot relevance check before calling an output verified.

**Confidence:** high for the optional/disabled path; no current MP4 was visually inspected in this audit.

### P2 — Per-file download limits exist, but no aggregate episode media budget was found

**Evidence:** `assets.py:29,68` caps an individual media download at 125,000,000 bytes. `music.py:11,14` caps an individual music download at 60,000,000 bytes. `tests/test_asset_download_budget.py` tests per-file limits and unrelated-result rejection. `generate.py` searches multiple queries across multiple beats, and I found no shared counter limiting total bytes or total downloaded clips across the whole episode.

**Impact:** many individually valid clips can still create a large total download, slow a run, or exhaust runner disk space.

**Fix:** introduce a configurable episode-wide byte/clip budget and stop searching once reached; record bytes, provider and skipped candidates in the run manifest/log. Add a test that verifies the budget is respected across multiple beats, not just for one file.

**Confidence:** medium-high; per-file controls are confirmed, aggregate control was not found in the inspected orchestration.

### P2 — Anthropic model configuration is inconsistent

**Evidence:** `env.example:8` documents `ANTHROPIC_MODEL=claude-3-5-sonnet-latest`, while `llm.py:253,309` defaults to `claude-sonnet-5-5`. The generation workflow passes `ANTHROPIC_API_KEY` but does not pass `ANTHROPIC_MODEL`, so a hosted run with only the key configured uses the code default rather than the example value.

**Impact:** Anthropic fallback can fail if the default identifier is not accepted by the configured API account, and the documented configuration does not reliably describe the runtime default.

**Fix:** choose one verified supported model ID, define it once, and pass the setting consistently through the workflow and local environment. Add a test for provider model selection. Do not assume a model ID is valid without a live provider check.

**Confidence:** high for the mismatch; whether the current default is accepted by Anthropic was not verified in this audit.

### P2 — Current automated tests do not establish finished-video quality

**Evidence:** the test suite covers manifest validation, asset filters, audio alignment, provider fallbacks, SFX, video-QC metadata, and code/workflow safety. `generate.py` has strong FFprobe checks, but the optional QC flag is off by default. The recent successful checks are unit/syntax/type checks, not a fresh end-to-end render followed by inspection of representative frames and narration synchronization.

**Fix:** add a lightweight deterministic render fixture to CI and a separate opt-in full generation acceptance run that uploads the MP4, manifest, plan, research, narration, alignment, QC report and a contact sheet. Review the artifact before treating a production run as visually verified.

**Confidence:** high about the distinction between unit tests and visual review; the repository may have older artifacts outside the recent runs inspected.

### P2 — Qwen/OpenCode repair execution has not yet demonstrated reliable completion

**Evidence:** repair run [#40130052647](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40130052647) failed with an OpenCode internal server error. Run [#40130117666](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40130117666) failed because the CLI invocation used an unsupported `--standalone` option. The invocation was corrected on a later branch, but run [#40130409503](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40130409503) remained in the OpenCode/Qwen step for over 30 minutes, with GitHub log download returning `BlobNotFound` while the job was still marked in progress. No repair PR from that run was confirmed during this audit.

**Fix:** keep the workflow isolated, add a shorter inference timeout and heartbeat/progress logging, save the raw Ollama/OpenCode logs continuously, and separate the audit-only task from code repair. Do not merge any agent changes until the diff and required tests are independently reviewed.

**Confidence:** high for the recorded run statuses/failures; the exact cause of the long-running step is not yet confirmed.

## 3. Recent Actions evidence

- On the intermediate footage-ranking branch, runs [#40132098335](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40132098335), [#40132098337](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40132098337), and [#40132098344](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40132098344) failed because two footage-selection tests expected `nanog` but got `computer`, and expected `auction-video` but got `auction-room`.
- The later fix was merged as [PR #60 / commit `89e2d44`](https://github.com/watfahamid-prog/jack-pockets/commit/89e2d44f0279274926d28a1a4538ff52260d19cd). The latest main-branch pipeline regression, validation, typecheck and footage-matching runs at that commit passed.
- The workflow-only audit-mode PR #62 has been merged. It changes no production video code.
- Qwen smoke-test verification had a separate OpenCode internal-server-error failure at [run #40130132597](https://github.com/watfahamid-prog/jack-pockets/actions/runs/40130132597).

## 4. Recommended order of work

1. Fix the Qwen/Gemini editor provider leak and add a regression test.
2. Fix caption phrase timing and add tests.
3. Enable routine video diagnostics and add a contact-sheet artifact.
4. Add an episode-wide asset download budget.
5. Align and verify the Anthropic model configuration.
6. Run the full documentary workflow; inspect the actual MP4, representative frames, audio, captions, shot relevance, manifest and source/licence metadata before rating the output.

**Do not mark the system fully verified yet.** Unit checks are useful and the latest main checks passed, but the end-to-end visual acceptance step remains outstanding.
