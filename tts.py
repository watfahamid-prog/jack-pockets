from __future__ import annotations
import asyncio
import os
from pathlib import Path

import edge_tts
from dotenv import load_dotenv

load_dotenv()

DEFAULT_VOICE = "en-US-GuyNeural"

async def _synthesize(text: str, out: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate=os.getenv("TTS_RATE", "+0%"),
        volume=os.getenv("TTS_VOLUME", "+0%"),
    )
    await communicate.save(str(out))

def synthesize(text: str, out: Path) -> Path:
    if not text.strip():
        raise RuntimeError("TTS received empty narration text")

    voice = os.getenv("TTS_VOICE") or DEFAULT_VOICE
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(_synthesize(text, out, voice))
    except Exception as exc:
        raise RuntimeError(
            f"TTS generation failed using Edge TTS voice '{voice}': {exc}"
        ) from exc

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("TTS returned no audio file")

    return out
