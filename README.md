# Jack Pockets Documentary Generator

An original long-form documentary pipeline built around a footage-led, restrained editorial style. The system is inspired by the broad visual principles of the Jack Pockets reference film supplied for this project: real subject-specific footage carries the story, archival/evidence material appears when useful, and simple graphics explain facts without turning the documentary into a slideshow.

It does **not** copy another creator's script, footage, graphics, or finished video.

## Pipeline

Topic → research → long-form story plan → narration → word alignment → subject-specific media search → sentence-level visual selection → restrained graphics/SFX → quality gate → Remotion render → MP4 validation.

## Run locally

Requirements: Python 3.11, Node.js 20, FFmpeg, and at least one supported LLM API key.

```bash
npm install
python -m pip install -r requirements.txt
cp env.example .env
npm run generate -- --topic "What Is the Most Expensive Thing Ever?"
```

The MP4 is written to `out/`. Intermediate research, narration, alignment, assets, and manifests are saved under `public/runs/`.

## GitHub Actions

Use `.github/workflows/generate-video.yml` and run **Generate Jack Pockets Style Documentary** with a topic.

## Providers

Required: at least one LLM provider key:
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

Recommended for real footage:
- `PEXELS_API_KEY`
- `PIXABAY_API_KEY`

The footage pipeline can also use Wikimedia Commons and Internet Archive where their metadata and licensing requirements are satisfied.

Optional narration:
- `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`
- OpenAI TTS when `OPENAI_API_KEY` is configured
- Edge TTS / Piper fallbacks

Optional research/music settings are documented in `env.example` and the workflow.

## Editorial rules

The current system is deliberately strict:

- Prefer literal, subject-specific moving footage over generic stock.
- Use archival/news footage for historical events, institutions, public events, and older technology when appropriate.
- Use photos only when moving footage is unavailable or the still image is genuinely the best evidence.
- Use maps, charts, documents, and screenshots only when the narration actually needs them.
- Never use generated b-roll/texture cards as filler.
- Never trust copied search-query metadata as proof that a clip matches the narration.
- Rank visuals against the asset's own metadata and apply a reuse penalty.
- Do not reuse the same visual in adjacent shots.
- Keep generated graphics below the quality-gate limit.
- Keep on-screen text short: names, dates, places, sources, or compact value labels.
- Keep captions and progress bars optional rather than making them part of the house look.
- Use restrained motion and SFX only when they have an editorial reason.
- Prefer an intentional quality-gate failure over rendering an irrelevant visual.

## Reference-style graphics

Essential numbers can appear as compact labels such as `TOTAL = $50B`. Labels are intentionally bright, sparse, and unboxed rather than large permanent cards. Generated evidence graphics should explain something that real footage cannot.

## Quality gates

A generation is rejected when it violates important visual constraints, including:

- under 8 minutes or over 30 minutes;
- incorrect 1920×1080 / 30fps output;
- missing narration/captions;
- too little real footage;
- too many generated graphics;
- generated filler roles such as generic b-roll cards;
- repeated visuals in adjacent shots;
- heavy reuse of one visual;
- overlapping shots;
- missing visual assets or invalid asset references;
- overlong text overlays.

The final render is also checked with FFprobe for video/audio streams, resolution, frame rate, and duration.

## Provenance

Every downloaded media item should retain its provider page URL, creator information when supplied, and licence information when supplied. Research sources and media sources are tracked separately. Automated provenance checks reduce risk but do not replace reviewing the actual source page before publishing.

## Reference audit

The public Jack Pockets reference video is treated as a **visual/editorial baseline**, not as evidence of the original creator's private production workflow or asset suppliers. The system uses its own licensed/open media sources and original graphics.

Continuous validation compiles Python modules before a generation run reaches API calls.

## Optional local-engine experiments (Qwen deliberately deferred)

The default production path remains unchanged. Experimental engines are opt-in and should be benchmarked on a real episode before being made defaults.

- **WhisperX alignment:** install only `requirements-whisperx.txt`, then set `JACKPOCKETS_ALIGNER=whisperx`. It runs on CPU in this configuration and may be slower; Faster-Whisper remains the default.
- **Kokoro local narration:** install `requirements-kokoro.txt` and set `TTS_PROVIDER=kokoro`. This explicitly selects local narration and does not fall back to paid TTS APIs if Kokoro fails. The first run may download model/voice assets.
- **Piper local narration:** set `TTS_PROVIDER=piper` to explicitly use the existing local Piper path.
- **Local semantic footage reranking:** set `JACKPOCKETS_SEMANTIC_RANKING=1`. Install `requirements-semantic-ranking.txt`; this downloads the configured sentence-transformer model on first use and adds semantic similarity to the existing lexical/reuse score. If the optional dependency or model fails, the pipeline logs the issue and uses the existing lexical ranker.
- **Finished-video diagnostics:** run `python video_qc.py out/your-video.mp4 --out out/video-qc.json`, or set `JACKPOCKETS_VIDEO_QC=1` to save diagnostics during generation. FFmpeg/FFprobe inspect stream metadata and long black segments; PySceneDetect adds scene-cut timings when installed (install `requirements-scene-qc.txt`). This is diagnostic only and never edits the video.

Do not install every optional package blindly on a low-memory machine. WhisperX/PyTorch is a large install, and the local tools use your computer's CPU/GPU and electricity. Optional engines are not yet approved for production until a fresh output has been measured and visually inspected. **Qwen local-LLM integration is intentionally postponed until these tools are tested.**

Install only the one optional requirements file for the experiment you are running. Do not install WhisperX, Kokoro, scene detection, and semantic ranking together by default; their dependencies and model downloads are independent.
