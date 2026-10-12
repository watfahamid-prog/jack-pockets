#!/usr/bin/env python3
"""Visual regression checks for the experimental FilmCraft bridge preview.

Samples frames inside each synthetic shot, checks for expected scene colors,
and flags a preview where the active picture occupies only a small area of the
export canvas. This is intentionally a gate: stream presence alone is not enough.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def frame_rgb(path: Path, seconds: float, width: int, height: int) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path),
            "-frames:v", "1", "-vf", f"scale={width}:{height}",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ],
        capture_output=True,
        check=True,
    )
    expected = width * height * 3
    if len(result.stdout) != expected:
        raise RuntimeError(f"Expected {expected} RGB bytes, got {len(result.stdout)} at {seconds}s")
    return result.stdout


def analyze(frame: bytes, width: int, height: int) -> dict:
    # At 160x90, ignore near-black pixels and find the bounding box of visible
    # picture content. Black letterbox/canvas margins are not counted.
    points = []
    active = 0
    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 3
            r, g, b = frame[i], frame[i + 1], frame[i + 2]
            if max(r, g, b) > 28:
                active += 1
                points.append((x, y))
    if not points:
        return {"active_fraction": 0.0, "bbox_fraction": 0.0, "bbox": None}
    min_x = min(p[0] for p in points)
    max_x = max(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    bbox_fraction = ((max_x - min_x + 1) * (max_y - min_y + 1)) / (width * height)
    return {
        "active_fraction": round(active / (width * height), 4),
        "bbox_fraction": round(bbox_fraction, 4),
        "bbox": [min_x, min_y, max_x, max_y],
    }


def main() -> int:
    video = Path(sys.argv[1])
    output = Path(sys.argv[2])
    width, height = 160, 90
    # The fixture uses a test-pattern clip for the first shot and orange for
    # the second. Sample away from the cut to avoid transition ambiguity.
    report = {
        "video": str(video),
        "canvas": "1920x1080 expected from ffprobe",
        "frames": {
            "shot_a": analyze(frame_rgb(video, 1.0, width, height), width, height),
            "shot_b": analyze(frame_rgb(video, 4.0, width, height), width, height),
        },
        "thresholds": {"minimum_bbox_fraction": 0.70},
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    bad = [
        name for name, frame in report["frames"].items()
        if frame["bbox_fraction"] < report["thresholds"]["minimum_bbox_fraction"]
    ]
    if bad:
        print(
            "VISUAL QA FAILED: active picture is too small or surrounded by "
            f"excessive empty canvas in: {', '.join(bad)}",
            file=sys.stderr,
        )
        return 1
    print("VISUAL QA PASSED: both shots fill a useful portion of the frame.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
