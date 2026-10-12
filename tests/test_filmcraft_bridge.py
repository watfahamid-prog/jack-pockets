import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filmcraft_bridge import build_plan


class FilmCraftBridgeTests(unittest.TestCase):
    def test_maps_local_video_shots_and_narration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            public = root / "public"
            (public / "runs" / "demo").mkdir(parents=True)
            (public / "runs" / "demo" / "clip.mp4").write_bytes(b"video")
            (public / "runs" / "demo" / "voice.wav").write_bytes(b"audio")
            manifest = {
                "title": "Bridge test",
                "duration": 8,
                "audioSrc": "runs/demo/voice.wav",
                "beats": [{
                    "start": 1,
                    "assets": [{"id": "v1", "kind": "video", "src": "runs/demo/clip.mp4"}],
                    "shots": [
                        {"start": 0, "end": 3, "assetIds": ["v1"], "layers": []},
                        {"start": 3, "end": 6, "assetIds": ["v1"], "layers": []},
                    ],
                }],
            }
            plan = build_plan(manifest, public, 5)
            self.assertEqual(len(plan["sources"]), 2)
            video = [p for p in plan["placements"] if p["kind"] == "video"]
            audio = [p for p in plan["placements"] if p["kind"] == "audio"]
            self.assertEqual([(p["start"], p["duration"]) for p in video], [(1.0, 3.0), (4.0, 1.0)])
            self.assertEqual(len(audio), 1)
            self.assertEqual(audio[0]["track"], "A1")

    def test_remote_or_missing_assets_are_not_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp) / "public"
            public.mkdir()
            manifest = {
                "duration": 4,
                "audioSrc": "https://example.com/voice.wav",
                "beats": [{
                    "start": 0,
                    "assets": [{"id": "remote", "kind": "video", "src": "https://example.com/clip.mp4"}],
                    "shots": [{"start": 0, "end": 2, "assetIds": ["remote"], "layers": []}],
                }],
            }
            with self.assertRaisesRegex(ValueError, "No local video assets"):
                build_plan(manifest, public, 4)


if __name__ == "__main__":
    unittest.main()
