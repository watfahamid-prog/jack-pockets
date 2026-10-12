from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from effectcraft_bridge import build_timeline


class EffectCraftBridgeTests(unittest.TestCase):
    def test_maps_local_video_and_narration_into_otio_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "clip.mp4").write_bytes(b"video")
            (root / "narration.mp3").write_bytes(b"audio")
            manifest = {
                "title": "Example documentary",
                "topic": "Example",
                "duration": 8,
                "fps": 30,
                "audioSrc": "clip.mp3" if False else "runs/narration.mp3",
                "beats": [{
                    "start": 0,
                    "assets": [{"id": "v1", "kind": "video", "src": "runs/clip.mp4", "title": "Example shot"}],
                    "shots": [{"start": 0, "end": 8, "assetIds": ["v1"], "layers": []}],
                }],
            }
            public = root / "public"
            (public / "runs").mkdir(parents=True)
            (public / "runs" / "clip.mp4").write_bytes(b"video")
            (public / "runs" / "narration.mp3").write_bytes(b"audio")
            timeline = build_timeline(manifest, public, 8)
            tracks = timeline["tracks"]["children"]
            self.assertEqual([track["kind"] for track in tracks], ["Video", "Audio"])
            self.assertEqual(tracks[0]["children"][0]["media_reference"]["target_url"], (public / "runs" / "clip.mp4").resolve().as_uri())
            self.assertEqual(tracks[1]["children"][0]["metadata"]["jack_pockets"]["kind"], "narration")
            self.assertEqual(tracks[0]["children"][0]["source_range"]["duration"]["value"], 240)

    def test_rejects_missing_narration_and_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "public"
            public.mkdir()
            manifest = {"duration": 5, "fps": 30, "audioSrc": "missing.mp3", "beats": [{"assets": [], "shots": []}]}
            with self.assertRaisesRegex(ValueError, "narration"):
                build_timeline(manifest, public, 5)

    def test_caps_preview_and_preserves_topic_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "public"
            (public / "runs").mkdir(parents=True)
            for name in ("clip.mp4", "narration.mp3"):
                (public / "runs" / name).write_bytes(b"media")
            manifest = {
                "topic": "Test topic", "duration": 100, "fps": 30, "audioSrc": "runs/narration.mp3",
                "beats": [{"start": 0, "assets": [{"id": "v", "kind": "video", "src": "runs/clip.mp4"}],
                           "shots": [{"start": 0, "end": 100, "assetIds": ["v"]}]}],
            }
            timeline = build_timeline(manifest, public, 12)
            self.assertEqual(timeline["metadata"]["jack_pockets"]["topic"], "Test topic")
            self.assertEqual(timeline["tracks"]["children"][0]["children"][0]["source_range"]["duration"]["value"], 360)


if __name__ == "__main__":
    unittest.main()
