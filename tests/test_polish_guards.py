import json
import tempfile
import unittest
from pathlib import Path

from editorial_brain import build_shots, keywords
from quality import validate


class PolishGuardsTests(unittest.TestCase):
    def _manifest(self, *, shots=None, source_urls=None, assets=None):
        shots = shots or [{
            "id": "beat-1-shot-0",
            "start": 0,
            "end": 60,
            "assetIds": ["video-1"],
            "layers": [{"kind": "image", "assetId": "video-1"}],
        }]
        assets = assets or [{
            "id": "video-1",
            "kind": "video",
            "role": "b-roll",
            "source_url": "https://example.com/video",
            "license": "Test license",
        }]
        beat = {
            "id": "beat-1",
            "start": 0,
            "end": 60,
            "narration": "A documented fact about the subject.",
            "source_urls": source_urls if source_urls is not None else ["https://example.com/source"],
            "assets": assets,
            "shots": shots,
        }
        return {
            "version": 2,
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "duration": 480,
            "audioSrc": "runs/test/narration.mp3",
            "captions": [{"word": "documented", "start": 0, "end": 0.5}],
            "sources": ["https://example.com/source"],
            "beats": [beat],
        }

    def test_rejects_missing_beat_evidence(self):
        manifest = self._manifest(source_urls=[])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate(str(path))
        self.assertTrue(any("no supporting source_urls" in error for error in errors))

    def test_rejects_visual_coverage_gap(self):
        manifest = self._manifest(shots=[
            {
                "id": "beat-1-shot-0",
                "start": 0,
                "end": 20,
                "assetIds": ["video-1"],
                "layers": [{"kind": "image", "assetId": "video-1"}],
            },
            {
                "id": "beat-1-shot-1",
                "start": 21,
                "end": 60,
                "assetIds": ["video-1"],
                "layers": [{"kind": "image", "assetId": "video-1"}],
            },
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate(str(path))
        self.assertTrue(any("visual coverage gap" in error for error in errors))

    def test_rejects_missing_asset_provenance(self):
        manifest = self._manifest(assets=[{"id": "video-1", "kind": "video", "role": "b-roll"}])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate(str(path))
        self.assertTrue(any("provenance gate" in error for error in errors))

    def test_sentence_keywords_normalize_plural_terms(self):
        terms = keywords("Cities and factories built bridges")
        self.assertIn("city", terms)
        self.assertIn("factory", terms)
        self.assertIn("bridge", terms)

    def test_build_shots_fills_alignment_pauses(self):
        beat = {
            "id": "beat-1",
            "start": 10,
            "end": 20,
            "narration": "First sentence. Second sentence.",
            "assets": [{
                "id": "video-1",
                "kind": "video",
                "title": "first second subject",
                "description": "first second subject",
                "tags": ["first", "second", "subject"],
                "role": "b-roll",
            }],
        }
        aligned = [
            {"word": "First", "start": 10.2, "end": 10.8},
            {"word": "sentence", "start": 10.9, "end": 11.5},
            {"word": "Second", "start": 13.0, "end": 13.6},
            {"word": "sentence", "start": 13.7, "end": 14.2},
        ]
        result = build_shots(beat, aligned_words=aligned)
        self.assertEqual(result["shots"][0]["start"], 0.0)
        self.assertEqual(result["shots"][-1]["end"], 10.0)
        for previous, current in zip(result["shots"], result["shots"][1:]):
            self.assertLessEqual(abs(previous["end"] - current["start"]), 0.001)


if __name__ == "__main__":
    unittest.main()
