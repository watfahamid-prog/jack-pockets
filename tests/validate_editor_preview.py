#!/usr/bin/env python3
"""Basic automated QA for short editor previews; not a substitute for human review."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate_editor_preview.py VIDEO REPORT.json")
    video = Path(sys.argv[1])
    report_path = Path(sys.argv[2])
    probe = json.loads(run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_type,codec_name,width,height,sample_rate,channels",
        "-of", "json", str(video),
    ]).stdout)
    streams = probe.get("streams", [])
    kinds = {stream.get("codec_type") for stream in streams}
    duration = float(probe.get("format", {}).get("duration", 0))
    if "video" not in kinds or "audio" not in kinds:
        raise SystemExit(f"QA failed: expected both video and audio streams, got {sorted(kinds)}")
    if duration < 5:
        raise SystemExit(f"QA failed: preview is too short ({duration:.2f}s)")
    audio = run(["ffmpeg", "-v", "info", "-i", str(video), "-vn", "-af", "volumedetect", "-f", "null", "-"], check=False)
    audio_log = (audio.stderr or b"").decode("utf-8", "replace")
    mean_line = next((line for line in audio_log.splitlines() if "mean_volume:" in line), "")
    if not mean_line:
        raise SystemExit("QA failed: could not measure audio volume")
    mean_text = mean_line.split("mean_volume:", 1)[1].strip().split()[0]
    if mean_text == "-inf" or float(mean_text) < -50:
        raise SystemExit(f"QA failed: audio appears silent ({mean_text} dB)")

    samples = []
    for second in sorted({min(1.0, duration / 4), min(4.0, duration / 2)}):
        frame = run([
            "ffmpeg", "-v", "error", "-ss", str(second), "-i", str(video),
            "-frames:v", "1", "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]).stdout
        if len(frame) != 160 * 90 * 3:
            raise SystemExit(f"QA failed: unable to decode frame at {second}s")
        active = 0
        xs, ys = [], []
        for i in range(0, len(frame), 3):
            r, g, b = frame[i:i + 3]
            if max(r, g, b) > 28:
                pixel = i // 3
                x, y = pixel % 160, pixel // 160
                active += 1
                xs.append(x)
                ys.append(y)
        bbox = 0 if not xs else ((max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)) / (160 * 90)
        samples.append({"time": second, "active_fraction": round(active / (160 * 90), 4), "bbox_fraction": round(bbox, 4)})
        if bbox < 0.70:
            raise SystemExit(f"QA failed: picture occupies too little of the frame at {second}s (bbox={bbox:.3f})")

    report = {
        "video": str(video),
        "duration_seconds": round(duration, 3),
        "bytes": int(probe.get("format", {}).get("size", video.stat().st_size)),
        "streams": streams,
        "audio_mean_volume": mean_text,
        "frame_samples": samples,
        "checks": {"video_and_audio": True, "audio_not_silent": True, "frames_decode": True, "picture_occupancy": True},
        "human_review_still_required": True,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
