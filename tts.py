from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path

import edge_tts
import requests
from dotenv import load_dotenv

load_dotenv()
DEFAULT_VOICE = "en-US-GuyNeural"


async def _synthesize_edge(text: str, out: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(
        text,
        voice=voice,
        rate=os.getenv("TTS_RATE", "+0%"),
        volume=os.getenv("TTS_VOLUME", "+0%"),
    )
    await communicate.save(str(out))


def _chunks(text: str, limit: int = 4200) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:limit])
            sentence = sentence[limit:]
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _synthesize_elevenlabs(text: str, out: Path, api_key: str, voice_id: str) -> None:
    voice_id = voice_id.strip()
    if not voice_id:
        raise RuntimeError("ELEVENLABS_API_KEY is set but ELEVENLABS_VOICE_ID is empty")
    temp_dir = out.parent / f".{out.stem}-elevenlabs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pieces = _chunks(text)
    if not pieces:
        raise RuntimeError("No narration text remained after chunking")

    list_file = temp_dir / "concat.txt"
    generated: list[Path] = []
    for index, piece in enumerate(pieces):
        part = temp_dir / f"part-{index:03d}.mp3"
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
            json={
                "text": piece,
                "model_id": os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
                "voice_settings": {
                    "stability": 0.48,
                    "similarity_boost": 0.78,
                    "style": 0.18,
                    "use_speaker_boost": True,
                },
            },
            params={"output_format": "mp3_44100_128"},
            timeout=150,
        )
        if not response.ok:
            raise RuntimeError(f"ElevenLabs HTTP {response.status_code}: {response.text[:500]}")
        part.write_bytes(response.content)
        if part.stat().st_size < 1000:
            raise RuntimeError(f"ElevenLabs returned an unexpectedly small audio chunk ({index + 1})")
        generated.append(part)

    out.parent.mkdir(parents=True, exist_ok=True)
    if len(generated) == 1:
        shutil.copyfile(generated[0], out)
    else:
        list_file.write_text(
            "".join("file '" + str(path.resolve()).replace("'", "'\\''") + "'\n" for path in generated),
            encoding="utf-8",
        )
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:a", "libmp3lame", "-q:a", "2", str(out)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    shutil.rmtree(temp_dir, ignore_errors=True)


def synthesize(text: str, out: Path) -> Path:
    if not text.strip():
        raise RuntimeError("TTS received empty narration text")
    out.parent.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if api_key and voice_id:
        try:
            _synthesize_elevenlabs(text, out, api_key, voice_id)
            print(f"[tts] narration generated with ElevenLabs voice ID {voice_id}", flush=True)
        except Exception as exc:
            raise RuntimeError(f"ElevenLabs narration failed: {exc}") from exc
    else:
        voice = os.getenv("TTS_VOICE") or DEFAULT_VOICE
        try:
            asyncio.run(_synthesize_edge(text, out, voice))
        except Exception as exc:
            raise RuntimeError(f"TTS generation failed using Edge TTS voice '{voice}': {exc}") from exc
        print(f"[tts] ElevenLabs key/voice ID not both configured; using Edge TTS voice {voice}", flush=True)

    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("TTS returned no audio file")
    return out
