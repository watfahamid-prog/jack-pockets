from __future__ import annotations

import json
from pathlib import Path


BANNED_GENERATED_ROLES = {"b-roll", "photo", "texture", "archival photo"}


def validate(path: str) -> list[str]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("version") != 2:
        errors.append("unsupported manifest version")
    beats = manifest.get("beats") or []
    if not beats:
        errors.append("manifest has no beats")
    if manifest.get("fps") != 30:
        errors.append("output must be 30fps to match the reference cadence and reduce render cost")
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

    asset_index = {}
    selected_asset_ids: list[str] = []
    selected_asset_counts: dict[str, int] = {}
    real_shots = 0
    total_shots = 0
    generated_shots = 0
    consecutive_same = 0
    previous_asset = ""

    for beat in beats:
        for asset in beat.get("assets", []):
            if asset.get("id"):
                asset_index[str(asset["id"])] = asset
        for shot in beat.get("shots", []):
            total_shots += 1
            ids = [str(x) for x in shot.get("assetIds", []) if x]
            for asset_id in ids:
                selected_asset_ids.append(asset_id)
                selected_asset_counts[asset_id] = selected_asset_counts.get(asset_id, 0) + 1
            chosen = [asset_index.get(x, {}) for x in ids]
            if any(a.get("kind") in {"video", "photo"} for a in chosen):
                real_shots += 1
            if any(a.get("kind") == "generated" for a in chosen):
                generated_shots += 1
                for asset in chosen:
                    if asset.get("kind") == "generated" and str(asset.get("role", "")).lower() in BANNED_GENERATED_ROLES:
                        errors.append(f"graphics gate: generated filler role is not allowed ({asset.get('id')})")
            primary = ids[0] if ids else ""
            if primary and primary == previous_asset:
                consecutive_same += 1
            previous_asset = primary

    selected_unique = set(selected_asset_ids)
    selected_assets = [asset_index[x] for x in selected_unique if x in asset_index]
    selected_videos = {str(a.get("id")) for a in selected_assets if a.get("kind") == "video"}
    if len(selected_videos) < 4:
        errors.append(f"footage gate: only {len(selected_videos)} distinct real video clips selected; need at least 4")

    real_ratio = real_shots / max(1, total_shots)
    if real_ratio < 0.55:
        errors.append(f"footage gate: only {real_ratio:.0%} of shots use real stock video/photos; need at least 55%")

    generated_ratio = generated_shots / max(1, total_shots)
    if generated_ratio > 0.40:
        errors.append(f"graphics gate: generated graphics fill {generated_ratio:.0%} of shots; maximum is 40%")

    if consecutive_same > 0:
        errors.append(f"repetition gate: {consecutive_same} consecutive shots reuse the same visual")

    heavy_reuse = sorted(
        ((count, asset_id) for asset_id, count in selected_asset_counts.items() if count >= 5),
        reverse=True,
    )
    if heavy_reuse:
        details = ", ".join(f"{asset_id}×{count}" for count, asset_id in heavy_reuse[:3])
        errors.append(f"repetition gate: a visual is reused 5+ times ({details})")

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
        assets = {str(asset.get("id")) for asset in beat.get("assets", []) if asset.get("id")}
        shots = beat.get("shots", [])
        if not shots:
            errors.append(f"beat has no shots: {beat_id}")
            continue
        previous_end = 0.0
        for shot in shots:
            shot_id = shot.get("id", "unknown")
            shot_start = float(shot.get("start", 0))
            shot_end = float(shot.get("end", 0))
            if shot_end <= shot_start:
                errors.append(f"invalid shot timing: {shot_id}")
            if shot_start < -0.05 or shot_end > end - start + 0.1:
                errors.append(f"shot outside beat: {shot_id}")
            if shot_start < previous_end - 0.05:
                errors.append(f"overlapping shots in beat {beat_id}: {shot_id}")
            previous_end = max(previous_end, shot_end)
            if not shot.get("layers"):
                errors.append(f"shot has no visual layers: {shot_id}")
            if not shot.get("assetIds"):
                errors.append(f"shot has no asset: {shot_id}")
            for layer in shot.get("layers", []):
                asset_id = layer.get("assetId")
                if asset_id and asset_id not in assets:
                    errors.append(f"missing asset reference: {shot_id} -> {asset_id}")
                if layer.get("kind") in {"label", "text"} and len(str(layer.get("text", ""))) > 70:
                    errors.append(f"text gate: overlay too long in {shot_id}")

    if duration > 0 and beats and abs(float(beats[-1].get("end", 0)) - duration) > 0.5:
        errors.append("manifest duration does not match final beat")
    return sorted(set(errors))
