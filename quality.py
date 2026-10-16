from __future__ import annotations

import json
from pathlib import Path

BANNED_GENERATED_ROLES = {"b-roll", "photo", "texture", "archival photo"}
MAX_VISUAL_REUSE = 4
MAX_GENERATED_RATIO = 0.40
MAX_PHOTO_RATIO = 0.15
MIN_REAL_VIDEO_CLIPS = 6
MIN_VIDEO_SHOT_RATIO = 0.70
MAX_STATIC_RUN = 1
MAX_COVERAGE_GAP = 0.35


def _as_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
    duration = _as_float(manifest.get("duration"))
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

    asset_index: dict[str, dict] = {}
    selected_asset_counts: dict[str, int] = {}
    total_shots = 0
    video_shots = 0
    photo_shots = 0
    generated_shots = 0
    consecutive_same = 0
    static_run = 0
    previous_asset = ""
    all_manifest_sources = {str(url) for url in (manifest.get("sources") or []) if url}

    for beat in beats:
        beat_id = str(beat.get("id", "unknown"))
        beat_sources = beat.get("source_urls")
        if not isinstance(beat_sources, list) or not beat_sources:
            errors.append(f"evidence gate: beat has no supporting source_urls: {beat_id}")
        else:
            for url in beat_sources:
                if not str(url).strip():
                    errors.append(f"evidence gate: empty source URL in {beat_id}")
                elif all_manifest_sources and str(url) not in all_manifest_sources:
                    errors.append(f"evidence gate: beat source is missing from manifest sources: {beat_id}")
        for asset in beat.get("assets", []):
            asset_id = str(asset.get("id") or "")
            if asset_id:
                asset_index[asset_id] = asset
        for shot in beat.get("shots", []):
            total_shots += 1
            ids = [str(x) for x in shot.get("assetIds", []) if x]
            for asset_id in ids:
                selected_asset_counts[asset_id] = selected_asset_counts.get(asset_id, 0) + 1
            chosen = [asset_index.get(x, {}) for x in ids]
            kinds = {str(a.get("kind", "")).lower() for a in chosen}
            if "video" in kinds:
                video_shots += 1
                static_run = 0
            elif kinds & {"photo", "generated", "document"}:
                if "photo" in kinds:
                    photo_shots += 1
                if "generated" in kinds:
                    generated_shots += 1
                static_run += 1
                if static_run > MAX_STATIC_RUN:
                    errors.append(f"motion gate: more than {MAX_STATIC_RUN} consecutive static-image shots near {shot.get('id')}")
            else:
                static_run += 1
            if "generated" in kinds:
                for asset in chosen:
                    if asset.get("kind") == "generated" and str(asset.get("role", "")).lower() in BANNED_GENERATED_ROLES:
                        errors.append(f"graphics gate: generated filler role is not allowed ({asset.get('id')})")
            for asset in chosen:
                kind = str(asset.get("kind", "")).lower()
                if kind in {"video", "photo"}:
                    if not asset.get("source_url"):
                        errors.append(f"provenance gate: real asset has no source_url ({asset.get('id')})")
                    if not asset.get("license"):
                        errors.append(f"provenance gate: real asset has no license ({asset.get('id')})")
            primary = ids[0] if ids else ""
            if primary and primary == previous_asset:
                consecutive_same += 1
            previous_asset = primary

    selected_unique = set(selected_asset_counts)
    selected_assets = [asset_index[x] for x in selected_unique if x in asset_index]
    selected_videos = {str(a.get("id")) for a in selected_assets if a.get("kind") == "video"}
    if len(selected_videos) < MIN_REAL_VIDEO_CLIPS:
        errors.append(f"footage gate: only {len(selected_videos)} distinct real video clips selected; need at least {MIN_REAL_VIDEO_CLIPS}")
    video_ratio = video_shots / max(1, total_shots)
    if video_ratio < MIN_VIDEO_SHOT_RATIO:
        errors.append(f"motion gate: only {video_ratio:.0%} of shots use moving video; need at least {MIN_VIDEO_SHOT_RATIO:.0%}")
    photo_ratio = photo_shots / max(1, total_shots)
    if photo_ratio > MAX_PHOTO_RATIO:
        errors.append(f"static-image gate: photos fill {photo_ratio:.0%} of shots; maximum is {MAX_PHOTO_RATIO:.0%}")
    generated_ratio = generated_shots / max(1, total_shots)
    if generated_ratio > MAX_GENERATED_RATIO:
        errors.append(f"graphics gate: generated graphics fill {generated_ratio:.0%} of shots; maximum is {MAX_GENERATED_RATIO:.0%}")
    if consecutive_same > 0:
        errors.append(f"repetition gate: {consecutive_same} consecutive shots reuse the same visual")
    heavy_reuse = sorted(((count, asset_id) for asset_id, count in selected_asset_counts.items() if count > MAX_VISUAL_REUSE), reverse=True)
    if heavy_reuse:
        details = ", ".join(f"{asset_id}×{count}" for count, asset_id in heavy_reuse[:3])
        errors.append(f"repetition gate: a visual is reused more than {MAX_VISUAL_REUSE} times ({details})")

    last_beat_end = 0.0
    for beat in beats:
        beat_id = str(beat.get("id", "unknown"))
        start = _as_float(beat.get("start"))
        end = _as_float(beat.get("end"))
        beat_duration = max(0.0, end - start)
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
            shot_id = str(shot.get("id", "unknown"))
            shot_start = _as_float(shot.get("start"))
            shot_end = _as_float(shot.get("end"))
            if shot_end <= shot_start:
                errors.append(f"invalid shot timing: {shot_id}")
            if shot_start < -0.05 or shot_end > beat_duration + 0.1:
                errors.append(f"shot outside beat: {shot_id}")
            if shot_start < previous_end - 0.05:
                errors.append(f"overlapping shots in beat {beat_id}: {shot_id}")
            if shot_start - previous_end > MAX_COVERAGE_GAP and previous_end > 0:
                errors.append(f"visual coverage gap in beat {beat_id}: {shot_id}")
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
        if shots:
            if _as_float(shots[0].get("start")) > MAX_COVERAGE_GAP:
                errors.append(f"visual coverage gap at beat start: {beat_id}")
            if beat_duration - _as_float(shots[-1].get("end")) > MAX_COVERAGE_GAP:
                errors.append(f"visual coverage gap at beat end: {beat_id}")
    if duration > 0 and beats and abs(_as_float(beats[-1].get("end")) - duration) > 0.5:
        errors.append("manifest duration does not match final beat")
    return sorted(set(errors))
