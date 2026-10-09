from __future__ import annotations

import os
import subprocess
from pathlib import Path

import requests


def get_music(query: str, out: Path, duration: float | None = None) -> Path | None:
    """Prepare a licensed/authorized direct audio URL as a looped music bed.

    MUSIC_URL must be a direct URL to audio the user is allowed to use. No track is
    downloaded from an unlicensed source or silently substituted.
    """
    url = os.getenv("MUSIC_URL", "").strip()
    if not url:
        return None

    out.parent.mkdir(parents=True, exist_ok=True)
    source = out.with_suffix(".source")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" in content_type:
        raise RuntimeError("MUSIC_URL returned a web page, not a direct audio file")
    with source.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    if source.stat().st_size < 2048:
        source.unlink(missing_ok=True)
        raise RuntimeError("MUSIC_URL returned an empty or invalid audio file")

    command = ["ffmpeg", "-y", "-i", str(source), "-vn"]
    if duration and duration > 0:
        command = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(source), "-t", f"{duration:.3f}", "-vn"]
    command += ["-c:a", "aac", "-b:a", "192k", str(out)]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.decode("utf-8", errors="replace")[-1200:] if exc.stderr else str(exc)
        raise RuntimeError(f"Could not prepare MUSIC_URL audio: {details}") from exc
    finally:
        source.unlink(missing_ok=True)

    if not out.exists() or out.stat().st_size < 2048:
        raise RuntimeError("Music preparation produced no usable audio file")
    return out
