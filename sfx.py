from __future__ import annotations

import subprocess
from pathlib import Path


def _render(command: list[str], output: Path) -> None:
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.decode("utf-8", errors="replace")[-1200:] if exc.stderr else str(exc)
        raise RuntimeError(f"Could not generate procedural sound effect {output.name}: {details}") from exc
    if not output.exists() or output.stat().st_size < 2048:
        raise RuntimeError(f"Generated sound effect is empty: {output.name}")


def create_sound_effects(out_dir: Path) -> dict[str, Path]:
    """Create subtle original transition/reveal accents; no external audio assets or keys needed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    whoosh = out_dir / "transition-whoosh.wav"
    hit = out_dir / "reveal-hit.wav"

    if not whoosh.exists():
        _render([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "anoisesrc=color=pink:duration=0.55:sample_rate=44100",
            "-af",
            "highpass=f=180,lowpass=f=6500,volume=0.13,"
            "afade=t=in:st=0:d=0.12,afade=t=out:st=0.25:d=0.30",
            "-ac", "2", "-c:a", "pcm_s16le", str(whoosh),
        ], whoosh)

    if not hit.exists():
        _render([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=82:duration=0.42:sample_rate=44100",
            "-f", "lavfi", "-i", "anoisesrc=color=pink:duration=0.42:sample_rate=44100",
            "-filter_complex",
            "[0:a]volume=0.30,afade=t=out:st=0.08:d=0.34[low];"
            "[1:a]lowpass=f=1200,volume=0.12,afade=t=out:st=0.02:d=0.20[noise];"
            "[low][noise]amix=inputs=2:normalize=0,alimiter=limit=0.7[out]",
            "-map", "[out]", "-ac", "2", "-c:a", "pcm_s16le", str(hit),
        ], hit)

    return {"whoosh": whoosh, "hit": hit}
