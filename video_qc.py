"""Local finished-video diagnostics for Jack Pockets.

Requires FFmpeg/FFprobe. PySceneDetect is optional; without it, stream metadata and
black-frame checks still run. This reports diagnostics and never changes the MP4.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def inspect_video(path: str, use_scene_detect: bool = True) -> dict:
    video = Path(path)
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg and FFprobe must be installed and available on PATH")

    # Keep a small file signature with the diagnostics so the run ledger can detect
    # reports that belong to an older file at the same path.
    file_stat = video.stat()
    raw = _run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height,r_frame_rate",
        "-of", "json", str(video),
    ])
    probe = json.loads(raw)
    streams = probe.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    duration = float((probe.get("format") or {}).get("duration") or 0)
    black_output = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(video), "-vf",
         "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    black_segments = [
        {"start": float(start), "end": float(end), "duration": float(length)}
        for start, end, length in re.findall(
            r"black_start:([0-9.]+)\s+black_end:([0-9.]+)\s+black_duration:([0-9.]+)",
            black_output.stderr,
        )
    ]
    scene_cuts = []
    scene_detection = "not_run"
    if use_scene_detect:
        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
            manager = SceneManager()
            manager.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))
            manager.detect_scenes(video=open_video(str(video)), show_progress=False)
            scenes = manager.get_scene_list()
            scene_cuts = [round(start.get_seconds(), 3) for start, _ in scenes[1:]]
            scene_detection = "ok"
        except ImportError:
            scene_detection = "not_installed"
        except Exception as exc:
            scene_detection = f"error: {type(exc).__name__}: {exc}"

    fps = video_stream.get("r_frame_rate", "0/1")
    if "/" in fps:
        numerator, denominator = fps.split("/", 1)
        fps_value = float(numerator) / max(float(denominator), 1.0)
    else:
        fps_value = float(fps or 0)
    report = {
        "file": str(video.resolve()),
        "file_size_bytes": file_stat.st_size,
        "file_mtime_ns": file_stat.st_mtime_ns,
        "duration_seconds": round(duration, 3),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": round(fps_value, 3),
        "has_audio": bool(audio_streams),
        "black_segments_over_0_5s": black_segments,
        "scene_detection": scene_detection,
        "scene_cut_count": len(scene_cuts),
        "scene_cut_times_seconds": scene_cuts,
        "warnings": [],
    }
    if not audio_streams:
        report["warnings"].append("No audio stream found")
    if duration <= 0:
        report["warnings"].append("Video duration is missing or invalid")
    if black_segments:
        report["warnings"].append("Detected long black segments; inspect them against intentional fades")
    if scene_detection == "not_installed":
        report["warnings"].append("PySceneDetect is not installed; scene-change analysis was skipped")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--out", default="")
    parser.add_argument("--skip-scenes", action="store_true")
    args = parser.parse_args()
    report = inspect_video(args.video, use_scene_detect=not args.skip_scenes)
    payload = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 1 if report["warnings"] and not report["has_audio"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
