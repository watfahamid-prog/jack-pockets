#!/usr/bin/env python3
"""Experimental adapter from a Jack Pockets manifest to a FilmCraft timeline.

This is deliberately opt-in: the normal Remotion/FFmpeg render path is unchanged.
Only local media files are imported; remote assets are reported and skipped.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def local_media_path(src: Any, public_dir: Path) -> Path | None:
    if not isinstance(src, str) or not src.strip() or src.startswith(("http://", "https://")):
        return None
    raw = Path(src)
    candidates = [raw] if raw.is_absolute() else [
        public_dir / raw,
        public_dir.parent / raw,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def build_plan(manifest: dict[str, Any], public_dir: Path, max_seconds: float) -> dict[str, Any]:
    if max_seconds <= 0:
        raise ValueError("max_seconds must be positive")
    beats = manifest.get("beats")
    if not isinstance(beats, list):
        raise ValueError("manifest must contain a beats array")

    placements: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    sources: list[dict[str, str]] = []
    source_by_path: dict[str, str] = {}

    def add_source(src: Any, kind: str, label: str) -> str | None:
        path = local_media_path(src, public_dir)
        if path is None:
            missing.append({"kind": kind, "label": label, "src": str(src or "")})
            return None
        key = str(path)
        if key not in source_by_path:
            source_by_path[key] = f"media-{len(sources) + 1}"
            sources.append({"id": source_by_path[key], "kind": kind, "path": key})
        return source_by_path[key]

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
            end = beat_start + float(shot.get("end", 0) or 0)
            if start >= max_seconds:
                continue
            duration = min(end, max_seconds) - start
            if duration <= 0:
                continue
            ids = list(shot.get("assetIds", []))
            ids.extend(
                layer.get("assetId")
                for layer in shot.get("layers", [])
                if isinstance(layer, dict) and layer.get("assetId")
            )
            chosen = None
            for asset_id in dict.fromkeys(str(value) for value in ids):
                asset = assets.get(asset_id)
                if not asset or asset.get("kind") != "video":
                    continue
                media_id = add_source(asset.get("src"), "video", f"beat {beat_index + 1}, shot {shot_index + 1}")
                if media_id:
                    chosen = (asset, media_id)
                    break
            if chosen:
                asset, media_id = chosen
                source_in = max(0.0, float(asset.get("sourceIn", 0) or 0))
                placements.append({
                    "media_id": media_id,
                    "kind": "video",
                    "track": "V1",
                    "start": round(start, 3),
                    "duration": round(duration, 3),
                    "source_in": round(source_in, 3),
                    "beat_index": beat_index,
                    "shot_index": shot_index,
                })
            else:
                missing.append({"kind": "video", "label": f"beat {beat_index + 1}, shot {shot_index + 1}", "src": "no available local video asset"})

    narration_id = add_source(manifest.get("audioSrc"), "audio", "narration")
    if narration_id:
        placements.append({
            "media_id": narration_id, "kind": "audio", "track": "A1",
            "start": 0.0, "duration": round(min(float(manifest.get("duration", max_seconds)), max_seconds), 3),
            "source_in": 0.0, "beat_index": -1, "shot_index": -1,
        })
    music_id = add_source(manifest.get("musicSrc"), "audio", "music") if manifest.get("musicSrc") else None
    if music_id:
        placements.append({
            "media_id": music_id, "kind": "audio", "track": "new",
            "start": 0.0, "duration": round(min(float(manifest.get("duration", max_seconds)), max_seconds), 3),
            "source_in": 0.0, "beat_index": -1, "shot_index": -1,
        })

    if not any(p["kind"] == "video" for p in placements):
        raise ValueError("No local video assets could be mapped from the manifest")
    return {
        "title": str(manifest.get("title") or manifest.get("topic") or "Jack Pockets experiment"),
        "duration": round(min(float(manifest.get("duration", max_seconds)), max_seconds), 3),
        "sources": sources,
        "placements": sorted(placements, key=lambda item: (item["start"], item["track"])),
        "missing": missing,
    }


def scale_video_clips_to_sequence(project_path: Path) -> int:
    """Scale imported timeline video clips to the sequence canvas before export.

    FilmCraft otherwise preserves 640x360 source dimensions in its 1920x1080
    default sequence, producing a small centered picture surrounded by black.
    """
    project = json.loads(project_path.read_text(encoding="utf-8"))
    items = project.get("project", {}).get("items", {})
    updated = 0
    for item in items.values():
        sequence = item.get("kind", {}).get("Sequence")
        if not isinstance(sequence, dict):
            continue
        for track in sequence.get("video_tracks", []):
            for clip in track.get("items", []):
                if clip.get("enabled", True) and clip.get("scale_to_frame") is not True:
                    clip["scale_to_frame"] = True
                    updated += 1
    if updated == 0:
        raise RuntimeError("No enabled video clips found to scale to the sequence frame")
    project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")
    return updated


def execute_plan(plan: dict[str, Any], cli: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_paths = [item["path"] for item in plan["sources"]]
    if not source_paths:
        raise ValueError("No media sources to import")
    project = (output_dir / "filmcraft-project.fcproj").resolve()
    import_cmd = [cli, "--demo", "--save-as", str(project), "import", *source_paths]
    imported = subprocess.run(import_cmd, text=True, capture_output=True, check=False)
    (output_dir / "import.stdout.txt").write_text(imported.stdout, encoding="utf-8")
    (output_dir / "import.stderr.txt").write_text(imported.stderr, encoding="utf-8")
    if imported.returncode:
        raise RuntimeError(f"FilmCraft import failed: {imported.stderr or imported.stdout}")
    try:
        ids = json.loads(imported.stdout).get("items", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        raise RuntimeError("FilmCraft import did not return JSON item IDs") from exc
    if len(ids) != len(source_paths):
        raise RuntimeError(f"FilmCraft imported {len(ids)} items for {len(source_paths)} source files")
    id_map = {source["id"]: item_id for source, item_id in zip(plan["sources"], ids)}
    (output_dir / "media-map.json").write_text(json.dumps(id_map, indent=2), encoding="utf-8")

    results = []
    for placement in plan["placements"]:
        params = {
            "item": id_map[placement["media_id"]],
            "track": placement["track"],
            "seconds": placement["start"],
            "duration": placement["duration"],
            "sourceIn": placement["source_in"],
            "video": placement["kind"] == "video",
            "audio": placement["kind"] == "audio",
        }
        result = subprocess.run(
            [cli, "--project", str(project), "exec", "timeline.place", json.dumps(params), "--save"],
            text=True, capture_output=True, check=False,
        )
        record = {**placement, "params": params, "returncode": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr}
        results.append(record)
        (output_dir / "placements.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"FilmCraft timeline placement failed: {result.stderr or result.stdout}")

    scaled = scale_video_clips_to_sequence(project)
    (output_dir / "scale-to-frame.json").write_text(
        json.dumps({"enabled_video_clips_scaled_to_sequence": scaled}, indent=2),
        encoding="utf-8",
    )

    export_path = (output_dir / "filmcraft-manifest-preview.mp4").resolve()
    result = subprocess.run(
        [cli, "--project", str(project), "export", str(export_path),
         "--start", "0", "--end", str(plan["duration"])],
        text=True, capture_output=True, check=False,
    )
    (output_dir / "export.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode or not export_path.is_file() or export_path.stat().st_size == 0:
        raise RuntimeError(f"FilmCraft export failed: {result.stderr or result.stdout}")
    return export_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--public-dir", type=Path, default=Path("public"))
    parser.add_argument("--output-dir", type=Path, default=Path("filmcraft-bridge-output"))
    parser.add_argument("--cli", default="./filmcraft-src/target/release/filmcraft-cli")
    parser.add_argument("--max-seconds", type=float, default=30.0, help="Cap preview duration; default 30 seconds")
    parser.add_argument("--plan-only", action="store_true", help="Write the plan without running FilmCraft")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    plan = build_plan(manifest, args.public_dir.resolve(), args.max_seconds)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "timeline-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(f"Mapped {len(plan['sources'])} local media files and {len(plan['placements'])} placements.")
    if plan["missing"]:
        print(f"Skipped {len(plan['missing'])} missing or remote media references.")
    if not args.plan_only:
        exported = execute_plan(plan, args.cli, args.output_dir)
        print(f"Exported experimental FilmCraft preview: {exported}")


if __name__ == "__main__":
    main()
