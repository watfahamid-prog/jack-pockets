import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import manifest

class ManifestTests(unittest.TestCase):
    def test_match_span_handles_contractions_and_continues_at_next_beat(self):
        words = [
            {"word": "We’re", "start": 0.0, "end": 0.3},
            {"word": "not", "start": 0.3, "end": 0.5},
            {"word": "done.", "start": 0.5, "end": 0.8},
            {"word": "Next", "start": 0.8, "end": 1.0},
            {"word": "story.", "start": 1.0, "end": 1.3},
        ]
        first_span = manifest.match_span("We're not done.", words, 0)
        second_span = manifest.match_span("Next story.", words, first_span[1])
        self.assertEqual(first_span, (0, 3))
        self.assertEqual(second_span, (3, 5))

    def test_build_enables_captions_and_preserves_aligned_words(self):
        plan = {"topic": "Test topic", "beats": [{"id": "b1", "narration": "Hello world.", "start": 0, "end": 480}]}
        words = [{"word": "Hello", "start": 0.0, "end": 2.0}, {"word": "world.", "start": 2.0, "end": 480.0}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            with patch.object(manifest, "refine_beat", side_effect=lambda beat: beat), patch.object(manifest, "build_shots", side_effect=lambda beat, **kwargs: beat):
                manifest.build(plan, "narration.mp3", words, [[]], {"fps": 30, "width": 1920, "height": 1080}, output)
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(data["showCaptions"])
        self.assertEqual(data["captions"], words)
        self.assertEqual(data["audioSrc"], "narration.mp3")

if __name__ == "__main__":
    unittest.main()
