from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def align(audio_path: str, out_path: str, model_name: str = "base.en"):
    from faster_whisper import WhisperModel

    print(f"[whisper] loading model: {model_name}", flush=True)
    started = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    print(
        f"[whisper] model ready in {time.time() - started:.1f}s; transcribing {audio_path}",
        flush=True,
    )

    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )

    words = []
    segment_count = 0
    for segment in segments:
        segment_count += 1
        segment_words = segment.words or []
        words.extend(
            {"word": w.word, "start": w.start, "end": w.end}
            for w in segment_words
        )
        if segment_count % 5 == 0:
            print(
                f"[whisper] processed {segment_count} segments / "
                f"{len(words)} words",
                flush=True,
            )

    if not words:
        raise RuntimeError("Whisper produced no word timestamps")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(words, indent=2), encoding="utf-8")

    duration = getattr(info, "duration", None)
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
    a = p.parse_args()
    align(a.audio, a.out, a.model)
