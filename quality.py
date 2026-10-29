from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

BANNED_GENERATED_ROLES = {"b-roll", "photo", "texture", "archival photo"}
STATIC_EVIDENCE_ROLES = {"map", "document", "screenshot", "chart", "archival photo"}
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


def _find_public_root(manifest_path: Path) -> Path:
    resolved = manifest_path.resolve()
    for parent in resolved.parents:
        if parent.name == "public":
            return parent
    return (Path.cwd() / "public").resolve()


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def _asset_source_error(asset: dict, public_root: Path) -> str | None:
    asset_id = str(asset.get("id") or "unknown")
    source = str(asset.get("src") or "").strip()
    if not source:
        return f"asset source gate: missing media src ({asset_id})"
    if source.startswith(("http://", "https://")):
        # External media can be intentional; do not make network requests during QC.
        return None

    source_path = Path(source)
    if source_path.is_absolute():
        resolved = source_path.resolve()
    else:
        resolved = (public_root / source_path).resolve()
    try:
        resolved.relative_to(public_root)
    except ValueError:
        return f"asset source gate: local media path escapes public directory ({asset_id})"
    if not resolved.is_file():
        return f"asset source gate: local media file does not exist ({asset_id}: {source})"
    return None


def validate(path: str) -> list[str]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    public_root = _find_public_root(manifest_path)
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
    raw_manifest_sources = manifest.get("sources") or []
    all_manifest_sources = {str(url).strip() for url in raw_manifest_sources if str(url).strip()}
    for source_url in sorted(all_manifest_sources):
        if not _is_http_url(source_url):
            errors.append("evidence gate: manifest contains an invalid source URL")

    for beat in beats:
        beat_id = str(beat.get("id", "unknown"))
        beat_sources = beat.get("source_urls")
        if not isinstance(beat_sources, list) or not beat_sources:
            errors.append(f"evidence gate: beat has no supporting source_urls: {beat_id}")
        else:
            for url in beat_sources:
                clean_url = str(url).strip()
                if not clean_url:
                    errors.append(f"evidence gate: empty source URL in {beat_id}")
                elif not _is_http_url(clean_url):
                    errors.append(f"evidence gate: invalid source URL in {beat_id}")
                elif clean_url not in all_manifest_sources:
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

            if not ids:
                errors.append(f"motion gate: shot has no visual asset: {shot.get('id')}")
            for asset in chosen:
                source_error = _asset_source_error(asset, public_root)
                if source_error:
                    errors.append(source_error)
                kind = str(asset.get("kind", "")).lower()
                role = str(asset.get("role", "")).lower()
                if kind in {"photo", "document"} and role not in STATIC_EVIDENCE_ROLES:
                    errors.append(f"motion gate: static asset used outside an evidence role ({asset.get('id')})")
                if kind == "generated" and role in BANNED_GENERATED_ROLES:
                    errors.append(f"graphics gate: generated filler role is not allowed ({asset.get('id')})")
                if kind in {"video", "photo"}:
                    source_url = str(asset.get("source_url") or "").strip()
                    if not source_url:
                        errors.append(f"provenance gate: real asset has no source_url ({asset.get('id')})")
                    elif not _is_http_url(source_url):
                        errors.append(f"provenance gate: real asset has invalid source_url ({asset.get('id')})")
                    license_text = str(asset.get("license") or "").strip()
                    if not license_text:
                        errors.append(f"provenance gate: real asset has no license ({asset.get('id')})")

                    license_url = str(asset.get("license_url") or "").strip()
                    if license_url and not _is_http_url(license_url):
                        errors.append(f"provenance gate: real asset has invalid license_url ({asset.get('id')})")
                    parsed_license = urlparse(license_url) if license_url and _is_http_url(license_url) else None
                    license_host = (parsed_license.hostname or "").lower().removeprefix("www.") if parsed_license else ""
                    license_path = parsed_license.path.rstrip("/") + "/" if parsed_license else ""
                    cc_by_url = license_host == "creativecommons.org" and license_path.startswith("/licenses/by/")
                    cc_by_label = bool(re.search(r"\bcc\s*by(?:\s|$)", license_text, re.IGNORECASE))
                    if (cc_by_url or cc_by_label) and not str(asset.get("creator") or asset.get("credit") or "").strip():
                        errors.append(f"provenance gate: CC BY asset has no creator credit ({asset.get('id')})")

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
    previous_beat_id = ""
    for beat in beats:
        beat_id = str(beat.get("id", "unknown"))
        start = _as_float(beat.get("start"))
        end = _as_float(beat.get("end"))
        beat_duration = max(0.0, end - start)
        if start < last_beat_end - 0.05:
            errors.append(f"overlapping beat: {beat_id}")
        if start - last_beat_end > MAX_COVERAGE_GAP:
            if previous_beat_id:
                errors.append(
                    f"visual coverage gap between beats {previous_beat_id} and {beat_id}: "
                    f"{start - last_beat_end:.2f}s"
                )
            else:
                errors.append(f"visual coverage gap at documentary start: {start:.2f}s")
        if end <= start:
            errors.append(f"invalid beat timing: {beat_id}")
        last_beat_end = end
        previous_beat_id = beat_id
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
