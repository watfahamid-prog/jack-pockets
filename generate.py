from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from assets import generate_role_asset, make_asset_plan, search_pexels, search_pexels_videos, search_pixabay, search_pixabay_videos, search_commons_videos, search_commons_photos, search_archive_videos
from llm import generate
from manifest import build
from music import get_music
from quality import validate
from research import search_web
from tts import synthesize

PROFILES = {"youtube": {"width": 1920, "height": 1080, "fps": 60}}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:55] or "run"


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
    # Research the subject before drafting, so the script is evidence-led rather than
    # generated first and decorated with search results afterwards.
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
        research.extend(found)

    # Include both research gathered before writing and beat-specific follow-up sources.
    plan["sources"] = list(dict.fromkeys(
        str(x["url"]) for x in research if isinstance(x, dict) and x.get("url")
    ))
    (root / "research.json").write_text(json.dumps(research, indent=2), encoding="utf-8")
    (root / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    narration = " ".join(str(beat.get("narration", "")).strip() for beat in plan.get("beats", []))
    audio = root / "narration.mp3"
    synthesize(narration, audio)

    # These scripts live at repository root. Calling scripts/*.py was a guaranteed failure.
    alignment = root / "alignment.json"
    subprocess.run(
        [sys.executable, "audio_aligner.py", str(audio), "--out", str(alignment)],
        check=True,
    )
    words = json.loads(alignment.read_text(encoding="utf-8"))

    asset_sets = []
    used_asset_ids: set[str] = set()
    for index, beat in enumerate(plan.get("beats", [])):
        title = str(beat.get("title", ""))
        beat_keywords = [str(x) for x in beat.get("keywords", []) if str(x).strip()]
        narration_text = str(beat.get("narration", "")).strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", narration_text)[0][:180]
        # Search using concise visual subjects rather than long narration sentences.
        queries = list(dict.fromkeys([
            beat_keywords[0] if beat_keywords else f"{title} archival footage",
            beat_keywords[1] if len(beat_keywords) > 1 else title,
        ]))
        stock_assets = []
        generated_assets = []

        for query in queries[:args.assets_per_beat]:
            try:
                videos = search_pexels_videos(query, root / f"assets-{index}", limit=4)
            except Exception as exc:
                print(f"[assets] video search failed for beat {index + 1}: {exc}", flush=True)
                videos = []

            candidates = videos
            # Prefer real moving footage from either free stock provider before photos.
            if not candidates:
                try:
                    candidates = search_pixabay_videos(query, root / f"assets-{index}", limit=4)
                except Exception as exc:
                    print(f"[assets] Pixabay video fallback failed for beat {index + 1}: {exc}", flush=True)
                    candidates = []
            if not candidates:
                try:
                    candidates = search_commons_videos(query, root / f"assets-{index}", limit=3)
                except Exception as exc:
                    print(f"[assets] Wikimedia video fallback failed for beat {index + 1}: {exc}", flush=True)
                    candidates = []
            # Free, keyless fallback for openly licensed real footage.
            if not candidates:
                try:
                    candidates = search_archive_videos(query, root / f"assets-{index}", limit=3)
                except Exception as exc:
                    print(f"[assets] Internet Archive video fallback failed for beat {index + 1}: {exc}", flush=True)
                    candidates = []
            if not candidates:
                try:
                    candidates = search_pexels(query, root / f"assets-{index}", limit=3)
                except Exception as exc:
                    print(f"[assets] Pexels photo fallback failed for beat {index + 1}: {exc}", flush=True)
                    candidates = []
            if not candidates:
                try:
                    candidates = search_pixabay(query, root / f"assets-{index}", limit=3)
                except Exception as exc:
                    print(f"[assets] Pixabay photo fallback failed for beat {index + 1}: {exc}", flush=True)
                    candidates = []
            if not candidates:
                try:
                    candidates = search_commons_photos(query, root / f"assets-{index}", limit=3)
                except Exception as exc:
                    print(f"[assets] Wikimedia photo fallback failed for beat {index + 1}: {exc}", flush=True)
                    candidates = []

            for item in candidates:
                asset_id = str(item.get("id", ""))
                if asset_id and asset_id in used_asset_ids:
                    continue
                if asset_id:
                    used_asset_ids.add(asset_id)
                item["query"] = query
                item["keywords"] = beat_keywords
                item["beat_title"] = title
                item["src"] = public_path(Path(item["src"]))
                stock_assets.append(item)

        for offset, role_plan in enumerate(make_asset_plan(narration_text, beat.get("editorial") or {})):
            item = generate_role_asset(
                role_plan["role"],
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
            f"[assets] beat={index + 1} footage={sum(x.get('kind') == 'video' for x in stock_assets)} "
            f"photos={sum(x.get('kind') == 'photo' for x in stock_assets)} graphics={len(generated_assets)}",
            flush=True,
        )
        asset_sets.append(beat_assets)

    manifest_path = root / "manifest.json"
    build(plan, public_path(audio), words, asset_sets, PROFILES[args.profile], manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

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

    # Remotion expects the component props shape { "manifest": ... }, not the raw manifest.
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
            "--pixel-format=yuv420p", "--crf=18", "--enforce-audio-track",
        ],
        check=True,
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
    if (video.get("width"), video.get("height")) != (1920, 1080):
        raise SystemExit("FINAL QC FAILED: output is not 1920x1080")
    if video.get("r_frame_rate") != "60/1":
        raise SystemExit("FINAL QC FAILED: output is not 60 FPS")
    duration = float(info.get("format", {}).get("duration", 0))
    if duration < 480 or duration > 1800:
        raise SystemExit(f"FINAL QC FAILED: duration {duration:.2f}s outside 8-30 minute range")
    print(f"FINAL QC PASSED: {out} | {duration:.2f}s | 1920x1080 | 60fps | audio=yes", flush=True)


if __name__ == "__main__":
    main()
