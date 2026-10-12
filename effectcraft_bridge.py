#!/usr/bin/env python3
"""Convert a Jack Pockets manifest into an OpenTimelineIO timeline for EffectCraft.

This is an opt-in integration path. It only references local media files and
never changes the normal Remotion/FFmpeg production render.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def local_media_path(src: Any, public_dir: Path) -> Path | None:
    if not isinstance(src, str) or not src.strip() or src.startswith(("http://", "https://")):
        return None
    raw = Path(src)
    candidates = [raw] if raw.is_absolute() else [public_dir / raw, public_dir.parent / raw]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def rt(seconds: float, fps: int) -> dict[str, Any]:
    return {"OTIO_SCHEMA": "RationalTime.1", "value": round(seconds * fps, 3), "rate": fps}


def gap(seconds: float, fps: int) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "Gap.1",
        "name": "Timeline gap",
        "source_range": {"OTIO_SCHEMA": "TimeRange.1", "start_time": rt(0, fps), "duration": rt(seconds, fps)},
        "effects": [], "markers": [], "metadata": {},
    }


def clip(path: Path, name: str, source_in: float, duration: float, fps: int, kind: str) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "Clip.2",
        "name": name,
        "media_reference": {
            "OTIO_SCHEMA": "ExternalReference.1",
            "target_url": path.as_uri(),
            "available_range": None,
            "metadata": {},
        },
        "source_range": {
            "OTIO_SCHEMA": "TimeRange.1",
            "start_time": rt(source_in, fps),
            "duration": rt(duration, fps),
        },
        "effects": [], "markers": [], "metadata": {"jack_pockets": {"kind": kind}},
    }


def make_track(name: str, kind: str, items: list[tuple[float, float, dict[str, Any]]], fps: int, end: float) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    cursor = 0.0
    for start, duration, item in sorted(items, key=lambda row: row[0]):
        if start > cursor + 0.001:
            children.append(gap(start - cursor, fps))
        if start < cursor - 0.001:
            raise ValueError(f"Overlapping {kind} placements at {start:.3f}s (previous ends {cursor:.3f}s)")
        children.append(item)
        cursor = max(cursor, start + duration)
    if end > cursor + 0.001:
        children.append(gap(end - cursor, fps))
    return {
        "OTIO_SCHEMA": "Track.1", "name": name, "kind": kind,
        "children": children, "source_range": None, "effects": [], "markers": [], "metadata": {},
    }


def build_timeline(manifest: dict[str, Any], public_dir: Path, max_seconds: float) -> dict[str, Any]:
    if max_seconds <= 0:
        raise ValueError("max_seconds must be positive")
    beats = manifest.get("beats")
    if not isinstance(beats, list) or not beats:
        raise ValueError("manifest must contain a non-empty beats array")
    fps = int(manifest.get("fps") or 30)
    if fps <= 0:
        raise ValueError("manifest fps must be positive")
    duration = min(float(manifest.get("duration") or 0), max_seconds)
    if duration <= 0:
        raise ValueError("manifest duration must be positive")

    video_items: list[tuple[float, float, dict[str, Any]]] = []
    audio_items: list[tuple[float, float, dict[str, Any]]] = []
    seen_video = 0
    missing: list[str] = []

    for beat_index, beat in enumerate(beats):
        if not isinstance(beat, dict):
            continue
        assets = {
            str(asset.get("id")): asset
            for asset in beat.get("assets", [])
            if isinstance(asset, dict) and asset.get("id") is not None
        }
        beat_start = float(beat.get("start", 0) or 0)
        for shot_index, shot in enumerate(beat.get("shots", [])):
            if not isinstance(shot, dict):
                continue
            start = beat_start + float(shot.get("start", 0) or 0)
            end = min(beat_start + float(shot.get("end", 0) or 0), duration)
            if start >= duration or end <= start:
                continue
            chosen = None
            ids = list(shot.get("assetIds", []))
            ids.extend(layer.get("assetId") for layer in shot.get("layers", []) if isinstance(layer, dict) and layer.get("assetId"))
            for asset_id in dict.fromkeys(str(value) for value in ids):
                asset = assets.get(asset_id)
                if not asset or asset.get("kind") != "video":
                    continue
                path = local_media_path(asset.get("src"), public_dir)
                if path:
                    chosen = (asset, path)
                    break
            if not chosen:
                missing.append(f"beat {beat_index + 1}, shot {shot_index + 1}")
                continue
            asset, path = chosen
            duration_s = end - start
            video_items.append((start, duration_s, clip(path, str(asset.get("title") or f"Beat {beat_index + 1} shot {shot_index + 1}"), float(asset.get("sourceIn", 0) or 0), duration_s, fps, "video")))
            seen_video += 1

    audio_path = local_media_path(manifest.get("audioSrc"), public_dir)
    if audio_path:
        audio_items.append((0.0, duration, clip(audio_path, "Narration", 0, duration, fps, "narration")))
    else:
        raise ValueError(f"Could not resolve local narration audioSrc: {manifest.get('audioSrc')!r}")
    if seen_video == 0:
        raise ValueError("No local video shots could be mapped from the manifest")

    tracks = [
        make_track("Jack Pockets Video", "Video", video_items, fps, duration),
        make_track("Narration", "Audio", audio_items, fps, duration),
    ]
    music_path = local_media_path(manifest.get("musicSrc"), public_dir) if manifest.get("musicSrc") else None
    if music_path:
        music_item = clip(music_path, "Music", 0, duration, fps, "music")
        tracks.append(make_track("Music", "Audio", [(0.0, duration, music_item)], fps, duration))

    return {
        "OTIO_SCHEMA": "Timeline.1",
        "name": str(manifest.get("title") or manifest.get("topic") or "Jack Pockets preview"),
        "global_start_time": None,
        "metadata": {"jack_pockets": {"topic": str(manifest.get("topic") or ""), "missing_video_shots": missing}},
        "tracks": {
            "OTIO_SCHEMA": "Stack.1", "name": "Tracks", "children": tracks,
            "source_range": None, "effects": [], "markers": [], "metadata": {},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--public-dir", type=Path, default=Path("public"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-seconds", type=float, default=20)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    timeline = build_timeline(manifest, args.public_dir, args.max_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "timeline": timeline["name"],
        "duration_seconds": min(float(manifest["duration"]), args.max_seconds),
        "video_clips": sum(len(track["children"]) for track in timeline["tracks"]["children"] if track["kind"] == "Video"),
        "tracks": [track["name"] for track in timeline["tracks"]["children"]],
        "missing_video_shots": timeline["metadata"]["jack_pockets"]["missing_video_shots"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
