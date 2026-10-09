# Jack Pockets Style Documentary Generator

An automated, original long-form documentary pipeline. It aims for the broad format of cinematic faceless documentary/edutainment videos: a strong opening, chapter-like story progression, relevant footage, narration, word-timed captions, restrained motion graphics, and a clear ending. It does not copy another channel's script or finished video.

## Pipeline

Topic → researched story plan → narration → word alignment → scene-specific footage search → editorial shot selection → optional soundtrack → manifest quality gate → Remotion render → audio/video stream checks.

## Run locally

Requirements: Python 3.11, Node.js 20, FFmpeg, and API credentials for the services you want to use.

```bash
npm install
python -m pip install -r requirements.txt
cp env.example .env
npm run generate -- --topic "Why the world's most expensive projects cost so much"
```

The generated MP4 is written to `out/`. Intermediate plans, narration, alignment, assets, and manifests are saved under `public/runs/`.

## GitHub Actions

The workflow is in `.github/workflows/generate-video.yml`. Open **Actions → Generate Jack Pockets Style Documentary → Run workflow** and enter a topic.

## Secrets and optional settings

Required: at least one LLM provider key (`GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`).

Recommended for real footage:
- `PEXELS_API_KEY` — searches for licensed stock video and photos.

Optional:
- `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` — both must be set to use ElevenLabs narration. If either is missing, the pipeline uses Edge TTS.
- `TAVILY_API_KEY` — research search.
- `MUSIC_URL` — direct URL to a royalty-free or otherwise authorized music file. The pipeline loops and encodes it to the documentary duration. No music is downloaded from an unlicensed source.

## Important implementation notes

- The Python entry points are at the repository root; the workflow and npm scripts use those actual paths.
- Remotion receives props in the required `{ "manifest": ... }` shape, so it renders the generated manifest rather than the demo.
- Scene selection scores assets against sentence keywords and avoids cycling through a fixed asset order.
- Generic keyword stickers, duplicated narration blocks, and gratuitous glitch/shake effects are intentionally limited.
- The quality gate checks structure, timing, captions, and audio source; final FFprobe checks verify a 1080p60 MP4 with an audio stream.

Stock search can still return weak matches, and high-quality footage depends on the available provider results and API quota. Always review the rendered artifact before publishing.


Continuous validation also compiles every Python module with `python -m compileall -q .` before a generation run can reach any API calls.
