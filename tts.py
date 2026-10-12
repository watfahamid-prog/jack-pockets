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



def _synthesize_openai(text: str, out: Path) -> None:
    """Generate narration with OpenAI TTS, chunking long scripts to API-safe lengths."""
    from openai import OpenAI

    client = OpenAI()
    temp_dir = out.parent / f".{out.stem}-openai-tts"
    temp_dir.mkdir(parents=True, exist_ok=True)
    pieces = _chunks(text, limit=3500)
    if not pieces:
        raise RuntimeError("No narration text remained after chunking")
    generated: list[Path] = []
    try:
        for index, piece in enumerate(pieces):
            part = temp_dir / f"part-{index:03d}.mp3"
            response = client.audio.speech.create(
                model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
                input=piece,
                response_format="mp3",
            )
            response.stream_to_file(str(part))
            if not part.exists() or part.stat().st_size < 1000:
                raise RuntimeError(f"OpenAI TTS returned an unexpectedly small audio chunk ({index + 1})")
            generated.append(part)
        if len(generated) == 1:
            shutil.copyfile(generated[0], out)
        else:
            list_file = temp_dir / "concat.txt"
            list_file.write_text(
                "".join("file '" + str(path.resolve()).replace("'", "'\\''") + "'\n" for path in generated),
                encoding="utf-8",
            )
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-c:a", "libmp3lame", "-q:a", "2", str(out)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



def _synthesize_piper(text: str, out: Path) -> None:
    """Generate narration locally with Piper when all cloud/network providers fail."""
    executable = shutil.which("piper")
    if not executable:
        raise RuntimeError("Piper executable is not installed")
    model = os.getenv("PIPER_MODEL", "en_US-libritts_r-medium").strip()
    temp_dir = out.parent / f".{out.stem}-piper"
    temp_dir.mkdir(parents=True, exist_ok=True)
    wav = temp_dir / "narration.wav"
    try:
        completed = subprocess.run(
            [executable, "--model", model, "--output_file", str(wav)],
            input=text,
            text=True,
            capture_output=True,
            timeout=int(os.getenv("PIPER_TIMEOUT_SECONDS", "600")),
            check=False,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "no diagnostic output")[-1200:]
            raise RuntimeError(f"Piper exited with code {completed.returncode}: {details}")
        if not wav.exists() or wav.stat().st_size < 1000:
            raise RuntimeError("Piper did not create a usable WAV file")
        if out.suffix.lower() == ".wav":
            shutil.copyfile(wav, out)
        else:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "2", str(out)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        if not out.exists() or out.stat().st_size < 1000:
            raise RuntimeError("Piper output conversion produced no usable audio")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def synthesize(text: str, out: Path) -> Path:
    if not text.strip():
        raise RuntimeError("TTS received empty narration text")
    out.parent.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if api_key and voice_id:
        try:
            _synthesize_elevenlabs(text, out, api_key, voice_id)
            print("[tts] narration generated with ElevenLabs", flush=True)
            return out
        except Exception as exc:
            errors.append(f"ElevenLabs: {exc}")
            print(f"[tts] ElevenLabs failed; trying configured fallback: {exc}", flush=True)
    elif api_key or voice_id:
        errors.append("ElevenLabs: both ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")

    if os.getenv("OPENAI_API_KEY", "").strip():
        try:
            _synthesize_openai(text, out)
            print(f"[tts] narration generated with OpenAI TTS ({os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts')})", flush=True)
            return out
        except Exception as exc:
            errors.append(f"OpenAI TTS: {exc}")
            print(f"[tts] OpenAI TTS failed; trying Edge TTS fallback: {exc}", flush=True)

    voice = os.getenv("TTS_VOICE") or DEFAULT_VOICE
    try:
        asyncio.run(_synthesize_edge(text, out, voice))
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("provider returned no audio file")
        print(f"[tts] narration generated with Edge TTS voice {voice}", flush=True)
        return out
    except Exception as exc:
        errors.append(f"Edge TTS ({voice}): {exc}")

    try:
        _synthesize_piper(text, out)
        print(f"[tts] narration generated locally with Piper ({os.getenv('PIPER_MODEL', 'en_US-libritts_r-medium')})", flush=True)
        return out
    except Exception as exc:
        errors.append(f"Piper: {exc}")

    raise RuntimeError(
        "All available narration providers failed. Configure a working ElevenLabs/OpenAI provider, "
        "restore Edge TTS connectivity, or ensure Piper and its voice model are available. Details: "
        + " | ".join(errors)
    )
