from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tts


class TTSFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "narration.mp3"
        self.env = patch.dict(os.environ, {
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "test-voice",
            "OPENAI_API_KEY": "test-openai-key",
            "TTS_VOICE": "en-US-GuyNeural",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_openai_fallback_is_used_when_elevenlabs_fails(self):
        def write_audio(text, out):
            Path(out).write_bytes(b"x" * 1200)

        with patch.object(tts, "_synthesize_elevenlabs", side_effect=RuntimeError("simulated outage")), \
             patch.object(tts, "_synthesize_openai", side_effect=write_audio), \
             patch.object(tts, "_synthesize_edge", side_effect=AssertionError("Edge should not be called")):
            result = tts.synthesize("A documentary narration.", self.out)
        self.assertEqual(result, self.out)
        self.assertGreater(self.out.stat().st_size, 1000)

    def test_edge_is_last_resort_when_openai_fails(self):
        async def write_audio(text, out, voice):
            Path(out).write_bytes(b"e" * 1200)

        with patch.object(tts, "_synthesize_elevenlabs", side_effect=RuntimeError("simulated outage")), \
             patch.object(tts, "_synthesize_openai", side_effect=RuntimeError("simulated outage")), \
             patch.object(tts, "_synthesize_edge", side_effect=write_audio):
            result = tts.synthesize("A documentary narration.", self.out)
        self.assertEqual(result, self.out)
        self.assertGreater(self.out.stat().st_size, 1000)

    def test_piper_is_used_when_cloud_and_edge_providers_fail(self):
        async def fail_edge(text, out, voice):
            raise RuntimeError("edge blocked")

        def write_piper(text, out):
            Path(out).write_bytes(b"p" * 1500)

        with patch.object(tts, "_synthesize_elevenlabs", side_effect=RuntimeError("quota exceeded")), \\
             patch.object(tts, "_synthesize_openai", side_effect=RuntimeError("no API credits")), \\
             patch.object(tts, "_synthesize_edge", side_effect=fail_edge), \\
             patch.object(tts, "_synthesize_piper", side_effect=write_piper):
            result = tts.synthesize("A documentary narration.", self.out)
        self.assertEqual(result, self.out)
        self.assertGreater(self.out.stat().st_size, 1000)

    def test_clear_error_when_all_providers_fail(self):
        with patch.object(tts, "_synthesize_elevenlabs", side_effect=RuntimeError("eleven down")), \
             patch.object(tts, "_synthesize_openai", side_effect=RuntimeError("openai down")), \
             patch.object(tts, "_synthesize_edge", side_effect=RuntimeError("edge down")):
            with self.assertRaisesRegex(RuntimeError, "All available narration providers failed"):
                tts.synthesize("A documentary narration.", self.out)


if __name__ == "__main__":
    unittest.main()
