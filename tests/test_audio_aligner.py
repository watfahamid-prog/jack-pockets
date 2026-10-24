import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audio_aligner


class AudioAlignerTests(unittest.TestCase):
    def test_rejects_unknown_backend_before_loading_optional_models(self):
        with self.assertRaisesRegex(ValueError, "backend"):
            audio_aligner.align("unused.wav", "unused.json", backend="not-a-backend")

    def test_writes_word_timestamps_from_faster_whisper(self):
        words = [{"word": " hello", "start": 0.1, "end": 0.4}]
        with tempfile.TemporaryDirectory() as directory, patch.object(audio_aligner, "_align_faster_whisper", return_value=(words, 1.0)):
            output = Path(directory) / "alignment.json"
            result = audio_aligner.align("unused.wav", str(output))
            self.assertEqual(result, output)
            self.assertEqual(__import__("json").loads(output.read_text(encoding="utf-8")), words)

    def test_rejects_empty_alignment(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audio_aligner, "_align_faster_whisper", return_value=([], 1.0)):
            with self.assertRaisesRegex(RuntimeError, "no word timestamps"):
                audio_aligner.align("unused.wav", str(Path(directory) / "alignment.json"))


if __name__ == "__main__":
    unittest.main()
