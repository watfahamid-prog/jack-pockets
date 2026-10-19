from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _align_faster_whisper(audio_path: str, model_name: str):
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )
    words = []
    for segment in segments:
        words.extend(
            {"word": w.word, "start": float(w.start), "end": float(w.end)}
            for w in (segment.words or [])
        )
    return words, getattr(info, "duration", None)


def _align_whisperx(audio_path: str, model_name: str):
    """Optional forced-alignment backend; install local-experiments-requirements.txt."""
    import whisperx

    audio = whisperx.load_audio(audio_path)
    model = whisperx.load_model(model_name, device="cpu", compute_type="int8")
    result = model.transcribe(audio, batch_size=2)
    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"], device="cpu"
    )
    aligned = whisperx.align(
        result["segments"], align_model, metadata, audio, device="cpu",
        return_char_alignments=False,
    )
    words = []
    for segment in aligned.get("segments", []):
        for word in segment.get("words", []):
            if word.get("start") is None or word.get("end") is None:
                continue
            token = str(word.get("word", "")).strip()
            if token:
                words.append({
                    "word": token,
                    "start": float(word["start"]),
                    "end": float(word["end"]),
                })
    return words, None


def align(audio_path: str, out_path: str, model_name: str = "base.en", backend: str = "faster-whisper"):

    backend = (backend or "faster-whisper").strip().lower()
    if backend not in {"faster-whisper", "whisperx"}:
        raise ValueError("ALIGNER backend must be 'faster-whisper' or 'whisperx'")
    print(f"[aligner] backend={backend}, model={model_name}", flush=True)
    started = time.time()
    if backend == "whisperx":
        words, duration = _align_whisperx(audio_path, model_name)
    else:
        words, duration = _align_faster_whisper(audio_path, model_name)
    print(
        f"[aligner] model/transcription finished in {time.time() - started:.1f}s",
        flush=True,
    )

    if not words:
        raise RuntimeError("Whisper produced no word timestamps")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(words, indent=2), encoding="utf-8")

    duration_text = f"{duration:.1f}s audio" if duration else "audio"
    print(
        f"[whisper] alignment complete: {len(words)} words, {duration_text}",
        flush=True,
    )
    print(out, flush=True)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("audio")
    p.add_argument("--out", default="alignment.json")
    p.add_argument("--model", default="base.en")
    p.add_argument(
        "--backend",
        choices=("faster-whisper", "whisperx"),
        default=os.getenv("JACKPOCKETS_ALIGNER", "faster-whisper"),
    )
    a = p.parse_args()
    align(a.audio, a.out, a.model, a.backend)
