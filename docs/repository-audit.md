# Jack Pockets repository audit

**Audit date:** 2026-10-25  
**Baseline:** `main` at `6e9783a` before the coding-agent cleanup branch.  
**Scope:** static source/configuration review. This audit does not claim that a newly generated MP4 has been visually inspected.

## Pipeline map

1. **Orchestration:** `generate.py` researches a topic, creates a documentary plan, generates narration, aligns words, selects assets, builds a manifest, renders the video and validates the MP4.
2. **Research:** `research.py`, `relevance.py` and `cache_utils.py` gather, rank and cache evidence.
3. **Story planning:** `llm.py` supports Gemini, OpenAI and Anthropic. The configured order is Gemini → OpenAI → Anthropic.
4. **Narration and alignment:** `tts.py` and `audio_aligner.py` handle TTS fallbacks and word-level timing.
5. **Media and editing:** `assets.py`, `editorial_brain.py`, `manifest.py` and `quality.py` search/rank media, plan shots and apply quality gates.
6. **Rendering and diagnostics:** Remotion renders the composition; FFprobe checks streams, dimensions, frame rate and duration. `video_qc.py` can add black-segment and scene-change diagnostics.
7. **Development agents:** repository instruction and skill surfaces support Claude Code and Codex. Local inference via Ollama is separate from documentary provider configuration.
8. **Run learning:** `harness2/` records outcomes, maintains an evidence ledger and proposes improvements. This is feedback machinery, not permission to auto-merge agent-authored code.

## Required verification

- Run `python -m compileall -q .` and `python -m unittest discover -s tests -v`.
- Run `npm run typecheck` for Remotion/TypeScript changes.
- Inspect the actual diff and relevant Actions logs before merging.
- For a video-generation change, inspect the MP4, representative frames, narration/audio synchronization, manifest, footage relevance and provenance. Unit tests alone do not prove finished-video quality.
- Avoid full documentary rendering merely to test a code-only change; it can consume substantial runner time, downloads and API quota.

## Open quality checks

1. **Captions:** word-level timestamp gaps can make captions flicker; verify phrase timing around pauses and punctuation.
2. **Visual relevance:** metadata ranking helps, but downloaded frames still need to be inspected against narration.
3. **Provider configuration:** keep documented model defaults, workflow environment and secrets aligned; verify hosted model identifiers before relying on them.
4. **Agent boundaries:** both agents must use project test gates, isolate changes and leave evidence; do not merge unreviewed patches.
5. **Cost control:** local inference uses the PC's resources and can avoid hosted model API charges. Cloud models and separately configured APIs may cost money. A hosted Actions runner cannot use Ollama on the user's PC through `localhost`.

**Status:** cleanup branch checks are pending. This audit does not claim the agents have been installed on the user's Windows PC or that the latest documentary has passed visual acceptance.
