from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from assets import generate_role_asset, make_asset_plan, search_pexels, search_pexels_videos, search_pixabay, search_pixabay_videos, search_commons_videos, search_commons_photos, search_archive_videos
from llm import generate
from manifest import build
from relevance import _asset_relevance, _asset_search_queries, _relevant_sources
from music import get_music
from quality import validate
from research import search_web
from sfx import create_sound_effects
from tts import synthesize

PROFILES = {"youtube": {"width": 1920, "height": 1080, "fps": 30}}
GENERATED_FILLER_ROLES = {"b-roll", "photo", "texture", "archival photo"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:55] or "run"


def _asset_query_limit(assets_per_beat: int) -> int:
    """Allow a third targeted query when the default two do not find enough clips."""
    return min(3, max(2, int(assets_per_beat) + 1))


def public_path(path: Path) -> str:
    return str(path.relative_to("public")).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an editorially planned documentary video.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--profile", choices=PROFILES, default="youtube")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--assets-per-beat", type=int, default=2)
    args = parser.parse_args()

    if args.assets_per_beat < 1 or args.assets_per_beat > 4:
        parser.error("--assets-per-beat must be between 1 and 4")

    root = Path("public/runs") / slug(args.topic)
    root.mkdir(parents=True, exist_ok=True)

    print(f"[pipeline] generating documentary: {args.topic}", flush=True)
    try:
        topic_research = search_web(
            f"{args.topic} primary sources scientific studies official records reliable evidence",
            limit=8,
        )
    except Exception as exc:
        print(f"[research] topic-level search unavailable: {exc}", flush=True)
        topic_research = []
    print(f"[research] topic-level sources found={len(topic_research)}", flush=True)
    plan = generate(args.topic, topic_research)
    plan["topic"] = args.topic
    plan["topicResearch"] = topic_research

    research = list(topic_research)
    for index, beat in enumerate(plan.get("beats", []), start=1):
        query = f"{args.topic}: {beat.get('title', '')} {str(beat.get('narration', ''))[:350]}"
        try:
            found = search_web(query, limit=3)
        except Exception as exc:
            print(f"[research] beat {index} search skipped: {exc}", flush=True)
            found = []
        beat["research"] = found
        verified_candidate_urls = _relevant_sources(args.topic, beat, [*topic_research, *found])
        beat["source_urls"] = verified_candidate_urls
        if not verified_candidate_urls:
            print(f"[research] beat {index}: no sufficiently relevant source found; claims need review", flush=True)
        research.extend(found)

    plan["sources"] = list(dict.fromkeys(
        str(x["url"]) for x in research if isinstance(x, dict) and x.get("url")
    ))
    (root / "research.json").write_text(json.dumps(research, indent=2), encoding="utf-8")
    (root / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    narration = " ".join(str(beat.get("narration", "")).strip() for beat in plan.get("beats", []))
    audio = root / "narration.mp3"
    synthesize(narration, audio)

    alignment = root / "alignment.json"
    subprocess.run(
        [sys.executable, "audio_aligner.py", str(audio), "--out", str(alignment)],
        check=True,
    )
    words = json.loads(alignment.read_text(encoding="utf-8"))

    asset_sets = []
    used_asset_ids: set[str] = set()
    for index, beat in enumerate(plan.get("beats", [])):
        title = str(beat.get("title", "")).strip()
        raw_keywords = beat.get("keywords", [])
        if isinstance(raw_keywords, str):
            raw_keywords = re.split(r"[,;|]", raw_keywords)
        beat_keywords = [str(x).strip() for x in raw_keywords if str(x).strip()]
        narration_text = str(beat.get("narration", "")).strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", narration_text)[0][:180]
        queries = _asset_search_queries(
            {**beat, "title": title, "keywords": beat_keywords, "narration": narration_text},
            # Start with two subject-first queries, but allow a third fallback when
            # the first two do not yield enough distinct relevant moving clips.
            limit=_asset_query_limit(args.assets_per_beat),
        )
        print(
            f"[assets] beat={index + 1}/{len(plan.get('beats', []))} subject={title!r} queries={len(queries)}",
            flush=True,
        )
        stock_assets = []
        generated_assets = []

        for query in queries:
            print(f"[assets] beat={index + 1} searching query={query!r}", flush=True)
            asset_dir = root / f"assets-{index}"
            videos = []
            providers = [
                ("Pexels", lambda: search_pexels_videos(query, asset_dir, limit=2, beat=beat)),
                ("Pixabay", lambda: search_pixabay_videos(query, asset_dir, limit=2, beat=beat)),
                ("Wikimedia Commons", lambda: search_commons_videos(query, asset_dir, limit=2, beat=beat)),
                ("Internet Archive", lambda: search_archive_videos(query, asset_dir, limit=2, beat=beat)),
            ]
            for provider_name, search in providers:
                if len(videos) >= 2:
                    break
                provider_started = time.monotonic()
                try:
                    found = search()
                except Exception as exc:
                    print(f"[assets] {provider_name} video search failed for beat {index + 1}: {exc}", flush=True)
                    found = []
                finally:
                    print(
                        f"[assets] provider={provider_name} beat={index + 1} elapsed={time.monotonic() - provider_started:.1f}s",
                        flush=True,
                    )
                for item in found:
                    relevant, matched_terms = _asset_relevance(query, beat, item)
                    if not relevant:
                        print(
                            f"[assets] rejected unrelated result provider={provider_name} "
                            f"beat={index + 1} title={str(item.get('title', ''))[:100]!r} "
                            f"matched={matched_terms}",
                            flush=True,
                        )
                        continue
                    if item.get("id") and item["id"] not in {x.get("id") for x in videos}:
                        videos.append(item)
                if len(videos) >= 2:
                    break

            candidates = videos
            if not candidates:
                print(
                    f"[assets] no relevant moving video for query={query[:100]!r}; "
                    "not substituting stock photos for b-roll",
                    flush=True,
                )

            for item in candidates:
                relevant, matched_terms = _asset_relevance(query, beat, item)
                if not relevant:
                    continue
                asset_id = str(item.get("id", ""))
                if asset_id and asset_id in used_asset_ids:
                    continue
                if asset_id:
                    used_asset_ids.add(asset_id)
                item["query"] = query
                item["keywords"] = beat_keywords
                item["beat_title"] = title
                item["beat_narration"] = first_sentence
                item["relevance_terms"] = matched_terms
                item["src"] = public_path(Path(item["src"]))
                stock_assets.append(item)

            # If enough distinct moving clips have been found, avoid extra provider
            # calls. Otherwise continue to the next, more specific query instead
            # of silently reusing one clip across many narration sentences.
            distinct_video_ids = {
                str(asset.get("id")) for asset in stock_assets
                if asset.get("kind") == "video" and asset.get("id")
            }
            if len(distinct_video_ids) >= 3:
                break

        # Generated graphics are explanatory evidence layers, not substitutes for footage.
        # Never manufacture fake "b-roll"/photo/texture/archival imagery just to satisfy a shot.
        for offset, role_plan in enumerate(make_asset_plan(narration_text, beat.get("editorial") or {})):
            role = str(role_plan.get("role", "")).strip().lower()
            if role in GENERATED_FILLER_ROLES:
                print(
                    f"[assets] skipped generated filler role={role!r} beat={index + 1}; "
                    "the quality gate requires real footage for b-roll roles",
                    flush=True,
                )
                continue
            item = generate_role_asset(
                role,
                narration_text,
                root / "generated",
                beat.get("research", []),
                index * 10 + offset,
            )
            if item:
                item["query"] = title
                item["keywords"] = beat_keywords
                item["src"] = public_path(Path(item["src"]))
                generated_assets.append(item)

        beat_assets = stock_assets + generated_assets
        print(
            f"[assets] beat={index + 1} moving_clips={sum(x.get('kind') == 'video' for x in stock_assets)} "
            f"photos={sum(x.get('kind') == 'photo' for x in stock_assets)} graphics={len(generated_assets)}",
            flush=True,
        )
        asset_sets.append(beat_assets)

    manifest_path = root / "manifest.json"
    build(plan, public_path(audio), words, asset_sets, PROFILES[args.profile], manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sound_effects = create_sound_effects(root / "sfx")
    for beat in manifest.get("beats", []):
        candidates = [
            shot for shot in beat.get("shots", [])
            if shot.get("reason") == "reveal" or shot.get("intent") == "consequence"
        ]
        if not candidates:
            continue
        shot = candidates[-1]
        effect_name = "hit" if shot.get("reason") == "reveal" else "whoosh"
        effect_path = sound_effects[effect_name]
        shot["sfx"] = [{
            "src": public_path(effect_path),
            "at": 0.72 if effect_name == "hit" else 0.12,
            "gain": 0.20 if effect_name == "hit" else 0.12,
            "label": "original procedural " + effect_name,
        }]
    manifest["soundDesign"] = {
        "provider": "Generated locally with FFmpeg",
        "effects": "Subtle transition/reveal accents on selected editorial beats",
        "external_assets": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    music_path = get_music("cinematic documentary ambient", root / "music-bed.m4a", manifest["duration"])
    if music_path:
        manifest["musicSrc"] = public_path(Path(music_path))
        music_metadata_path = Path(music_path).with_suffix(".json")
        if music_metadata_path.exists():
            music_metadata = json.loads(music_metadata_path.read_text(encoding="utf-8"))
            manifest["musicSource"] = music_metadata
            source_url = music_metadata.get("source_url")
            if source_url:
                manifest["sources"] = list(dict.fromkeys([*(manifest.get("sources") or []), source_url]))
            print(
                f"[music] soundtrack prepared: {manifest['musicSrc']} "
                f"| provider={music_metadata.get('provider', 'unknown')} "
                f"| license={music_metadata.get('license', 'not stated')}",
                flush=True,
            )
        else:
            print(f"[music] soundtrack prepared: {manifest['musicSrc']}", flush=True)
    else:
        print("[music] no soundtrack available; rendering narration only", flush=True)

    errors = validate(str(manifest_path))
    if errors:
        raise SystemExit("QUALITY GATE FAILED:\n" + "\n".join(errors))

    props_path = root / "render-props.json"
    props_path.write_text(json.dumps({"manifest": manifest}, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"READY: {manifest_path}", flush=True)
    if args.no_render:
        return

    out = Path("out") / f"{slug(args.topic)}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "npx", "remotion", "render", "index.tsx", "JackPocketsVideo", str(out),
            "--props", str(props_path), "--codec=h264", "--audio-codec=aac",
            "--pixel-format=yuv420p", "--crf=20", "--enforce-audio-track",
        ],
        check=True,
    )

    if not out.exists() or out.stat().st_size < 100_000:
        raise RuntimeError(f"Render produced no usable MP4: {out}")
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height,avg_frame_rate",
            "-of", "json", str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    media = json.loads(probe.stdout)
    video_streams = [item for item in media.get("streams", []) if item.get("codec_type") == "video"]
    audio_streams = [item for item in media.get("streams", []) if item.get("codec_type") == "audio"]
    if not video_streams:
        raise RuntimeError("Rendered MP4 has no video stream")
    if not audio_streams:
        raise RuntimeError("Rendered MP4 has no audio stream")
    video_stream = video_streams[0]
    expected = PROFILES[args.profile]
    if (video_stream.get("width"), video_stream.get("height")) != (expected["width"], expected["height"]):
        raise RuntimeError(
            f"Rendered dimensions are {video_stream.get('width')}x{video_stream.get('height')}; "
            f"expected {expected['width']}x{expected['height']}"
        )
    rate = str(video_stream.get("avg_frame_rate") or "0/0")
    try:
        numerator, denominator = rate.split("/", 1)
        actual_fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        actual_fps = 0.0
    if abs(actual_fps - expected["fps"]) > 0.1:
        raise RuntimeError(f"Rendered frame rate is {rate}; expected {expected['fps']} fps")
    actual_duration = float((media.get("format") or {}).get("duration") or 0)
    if actual_duration < 480 or actual_duration > 1800:
        raise RuntimeError(f"Rendered duration {actual_duration:.1f}s is outside the 8–30 minute gate")
    if abs(actual_duration - float(manifest["duration"])) > 5:
        raise RuntimeError(
            f"Rendered duration {actual_duration:.1f}s differs from manifest "
            f"{float(manifest['duration']):.1f}s by more than 5s"
        )
    print(
        f"[quality] rendered MP4 verified: {actual_duration / 60:.2f} min, "
        f"{expected['width']}x{expected['height']} at {actual_fps:.0f} fps, "
        f"audio stream present, {out.stat().st_size / (1024 * 1024):.1f} MiB",
        flush=True,
    )

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    streams = info.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video or not audio_stream:
        raise SystemExit("FINAL QC FAILED: missing video or audio stream")
    expected = PROFILES[args.profile]
    if (video.get("width"), video.get("height")) != (expected["width"], expected["height"]):
        raise SystemExit(
            f"FINAL QC FAILED: output is not {expected['width']}x{expected['height']}"
        )
    rate = str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/0")
    try:
        numerator, denominator = rate.split("/", 1)
        actual_fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        actual_fps = 0.0
    if abs(actual_fps - expected["fps"]) > 0.1:
        raise SystemExit(
            f"FINAL QC FAILED: output is {actual_fps:g} FPS; expected {expected['fps']} FPS"
        )
    duration = float(info.get("format", {}).get("duration", 0))
    if duration < 480 or duration > 1800:
        raise SystemExit(f"FINAL QC FAILED: duration {duration:.2f}s outside 8-30 minute range")
    print(
        f"FINAL QC PASSED: {out} | {duration:.2f}s | "
        f"{expected['width']}x{expected['height']} | {actual_fps:g}fps | audio=yes",
        flush=True,
    )

    if os.getenv("JACKPOCKETS_VIDEO_QC", "").strip().lower() in {"1", "true", "yes"}:
        try:
            from video_qc import inspect_video
            qc_report = inspect_video(str(out))
            qc_path = root / "video-qc.json"
            qc_path.write_text(json.dumps(qc_report, indent=2), encoding="utf-8")
            print(f"[video-qc] diagnostics saved to {qc_path}", flush=True)
            for warning in qc_report.get("warnings", []):
                print(f"[video-qc] warning: {warning}", flush=True)
        except Exception as exc:
            # The existing mandatory FFprobe checks above remain authoritative.
            # Optional scene/black-frame diagnostics must not invalidate a valid render.
            print(f"[video-qc] optional diagnostics failed: {exc}", flush=True)


if __name__ == "__main__":
    main()
