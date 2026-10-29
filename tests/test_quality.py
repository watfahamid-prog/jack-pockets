import json
import tempfile
import unittest
from pathlib import Path

from quality import validate


class QualityGateTests(unittest.TestCase):
    def _write(self, manifest):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(manifest, tmp)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def _base(self):
        return {
            "version": 2,
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "duration": 480,
            "audioSrc": "narration.mp3",
            "captions": [{"word": "hello", "start": 0, "end": 1}],
            "beats": [],
        }

    def test_rejects_consecutive_duplicate_visuals(self):
        manifest = self._base()
        asset = {"id": "v1", "kind": "video", "role": "b-roll"}
        shots = [
            {"id": "s1", "start": 0, "end": 2, "assetIds": ["v1"], "layers": [{"kind": "image", "assetId": "v1"}]},
            {"id": "s2", "start": 2.1, "end": 4, "assetIds": ["v1"], "layers": [{"kind": "image", "assetId": "v1"}]},
        ]
        manifest["beats"] = [{"id": "b1", "start": 0, "end": 480, "assets": [asset], "shots": shots}]
        errors = validate(self._write(manifest))
        self.assertTrue(any("consecutive shots reuse" in error for error in errors))

    def test_rejects_generated_filler_role(self):
        manifest = self._base()
        asset = {"id": "g1", "kind": "generated", "role": "b-roll"}
        shots = [{"id": "s1", "start": 0, "end": 480, "assetIds": ["g1"], "layers": [{"kind": "image", "assetId": "g1"}]}]
        manifest["beats"] = [{"id": "b1", "start": 0, "end": 480, "assets": [asset], "shots": shots}]
        errors = validate(self._write(manifest))
        self.assertTrue(any("generated filler role" in error for error in errors))

    def test_rejects_uncovered_gaps_between_beats(self):
        manifest = self._base()
        asset1 = {"id": "v1", "kind": "video", "role": "b-roll", "source_url": "https://example.test/v1", "license": "test"}
        asset2 = {"id": "v2", "kind": "video", "role": "b-roll", "source_url": "https://example.test/v2", "license": "test"}
        manifest["beats"] = [
            {"id": "b1", "start": 0, "end": 10, "source_urls": ["https://example.test/source"], "assets": [asset1],
             "shots": [{"id": "s1", "start": 0, "end": 10, "assetIds": ["v1"], "layers": [{"kind": "image", "assetId": "v1"}]}]},
            {"id": "b2", "start": 10.6, "end": 480, "source_urls": ["https://example.test/source"], "assets": [asset2],
             "shots": [{"id": "s2", "start": 0, "end": 469.4, "assetIds": ["v2"], "layers": [{"kind": "image", "assetId": "v2"}]}]},
        ]
        errors = validate(self._write(manifest))
        self.assertTrue(any("visual coverage gap between beats b1 and b2" in error for error in errors))

    def test_rejects_overlapping_shots(self):
        manifest = self._base()
        assets = [
            {"id": "v1", "kind": "video", "role": "b-roll"},
            {"id": "v2", "kind": "video", "role": "b-roll"},
            {"id": "v3", "kind": "video", "role": "b-roll"},
            {"id": "v4", "kind": "video", "role": "b-roll"},
        ]
        shots = [
            {"id": "s1", "start": 0, "end": 3, "assetIds": ["v1"], "layers": [{"kind": "image", "assetId": "v1"}]},
            {"id": "s2", "start": 2.5, "end": 5, "assetIds": ["v2"], "layers": [{"kind": "image", "assetId": "v2"}]},
        ]
        manifest["beats"] = [{"id": "b1", "start": 0, "end": 480, "assets": assets, "shots": shots}]
        errors = validate(self._write(manifest))
        self.assertTrue(any("overlapping shots" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
