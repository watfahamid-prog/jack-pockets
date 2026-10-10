from __future__ import annotations

import json
from pathlib import Path


def validate(path: str) -> list[str]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("version") != 2:
        errors.append("unsupported manifest version")
    beats = manifest.get("beats") or []
    if not beats:
        errors.append("manifest has no beats")
    if manifest.get("fps") != 60:
        errors.append("output must be 60fps")
    if (manifest.get("width"), manifest.get("height")) != (1920, 1080):
        errors.append("output must be 1920x1080")

    duration = float(manifest.get("duration", 0))
    if duration < 480:
        errors.append(f"documentary is under 8 minutes ({duration:.1f}s)")
    if duration > 1800:
        errors.append("documentary exceeds 30 minutes")
    if duration <= 0:
        errors.append("duration must be positive")
    if len(beats) < 8:
        errors.append("long-form documentary needs at least 8 beats")
    if not manifest.get("captions"):
        errors.append("missing Whisper captions")
    if not manifest.get("audioSrc"):
        errors.append("missing narration audio source")

    # A successful render must be footage-led, not just a slideshow of generated cards.
    asset_index = {}
    selected_asset_ids = set()
    for beat in beats:
        for asset in beat.get("assets", []):
            if asset.get("id"):
                asset_index[str(asset["id"])] = asset
        for shot in beat.get("shots", []):
            selected_asset_ids.update(str(x) for x in shot.get("assetIds", []) if x)
    selected_assets = [asset_index[x] for x in selected_asset_ids if x in asset_index]
    selected_videos = {str(a.get("id")) for a in selected_assets if a.get("kind") == "video"}
    real_shots = 0
    total_shots = 0
    for beat in beats:
        for shot in beat.get("shots", []):
            total_shots += 1
            chosen = [asset_index.get(str(x), {}) for x in shot.get("assetIds", [])]
            if any(a.get("kind") in {"video", "photo"} for a in chosen):
                real_shots += 1
    if len(selected_videos) < 4:
        errors.append(f"footage gate: only {len(selected_videos)} distinct real video clips selected; need at least 4")
    real_ratio = real_shots / max(1, total_shots)
    if real_ratio < 0.55:
        errors.append(f"footage gate: only {real_ratio:.0%} of shots use real stock video/photos; need at least 55%")

    last_beat_end = 0.0
    for beat in beats:
        beat_id = beat.get("id", "unknown")
        start = float(beat.get("start", 0))
        end = float(beat.get("end", 0))
        if start < last_beat_end - 0.05:
            errors.append(f"overlapping beat: {beat_id}")
        if end <= start:
            errors.append(f"invalid beat timing: {beat_id}")
        last_beat_end = end
        assets = {asset.get("id") for asset in beat.get("assets", [])}
        shots = beat.get("shots", [])
        if not shots:
            errors.append(f"beat has no shots: {beat_id}")
        for shot in shots:
            shot_id = shot.get("id", "unknown")
            shot_start = float(shot.get("start", 0))
            shot_end = float(shot.get("end", 0))
            if shot_end <= shot_start:
                errors.append(f"invalid shot timing: {shot_id}")
            if shot_start < -0.05 or shot_end > end - start + 0.1:
                errors.append(f"shot outside beat: {shot_id}")
            if not shot.get("layers"):
                errors.append(f"shot has no visual layers: {shot_id}")
            if not shot.get("assetIds"):
                errors.append(f"shot has no asset: {shot_id}")
            for layer in shot.get("layers", []):
                asset_id = layer.get("assetId")
                if asset_id and asset_id not in assets:
                    errors.append(f"missing asset reference: {shot_id} -> {asset_id}")

    if duration > 0 and beats and abs(float(beats[-1].get("end", 0)) - duration) > 0.5:
        errors.append("manifest duration does not match final beat")
    return sorted(set(errors))
