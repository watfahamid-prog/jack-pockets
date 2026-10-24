import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sfx

class SoundEffectsTests(unittest.TestCase):
    def test_creates_both_effects_using_ffmpeg_and_reuses_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "transition-whoosh.wav").write_bytes(b"x" * 2048)
            (out / "reveal-hit.wav").write_bytes(b"y" * 2048)
            with patch.object(sfx, "_render") as render:
                result = sfx.create_sound_effects(out)
            self.assertEqual(set(result), {"whoosh", "hit"})
            render.assert_not_called()

    def test_empty_generated_effect_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "empty.wav"
            with patch.object(sfx.subprocess, "run", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "empty"):
                    sfx._render(["ffmpeg"], output)

if __name__ == "__main__":
    unittest.main()
