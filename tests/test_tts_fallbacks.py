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
            "TTS_PROVIDER": "auto",
            # Unit tests must exercise the mocked providers, not reuse a runner's
            # persistent narration cache from an earlier workflow run.
            "JACKPOCKETS_DISABLE_CACHE": "1",
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

        with (
            patch.object(tts, "_synthesize_elevenlabs", side_effect=RuntimeError("quota exceeded")),
            patch.object(tts, "_synthesize_openai", side_effect=RuntimeError("no API credits")),
            patch.object(tts, "_synthesize_edge", side_effect=fail_edge),
            patch.object(tts, "_synthesize_piper", side_effect=write_piper),
        ):
            result = tts.synthesize("A documentary narration.", self.out)
        self.assertEqual(result, self.out)
        self.assertGreater(self.out.stat().st_size, 1000)

    def test_clear_error_when_all_providers_fail(self):
        with (
            patch.object(tts, "_synthesize_elevenlabs", side_effect=RuntimeError("eleven down")),
            patch.object(tts, "_synthesize_openai", side_effect=RuntimeError("openai down")),
            patch.object(tts, "_synthesize_edge", side_effect=RuntimeError("edge down")),
            patch.object(tts, "_synthesize_piper", side_effect=RuntimeError("piper down")),
        ):
            with self.assertRaisesRegex(RuntimeError, "All available narration providers failed"):
                tts.synthesize("A documentary narration.", self.out)

    def test_audio_cache_key_tracks_synthesis_settings(self):
        base = {
            "JACKPOCKETS_CACHE_DIR": "test-cache",
            "TTS_PROVIDER": "auto",
            "TTS_VOICE": "en-US-GuyNeural",
            "TTS_RATE": "+0%",
            "TTS_VOLUME": "+0%",
            "PIPER_MODEL": "en_US-lessac-medium",
            "KOKORO_SPEED": "1.0",
        }
        with patch.dict(os.environ, base, clear=True):
            original = tts._audio_cache_path("A documentary narration.")

        for setting, changed_value in (
            ("TTS_RATE", "+10%"),
            ("TTS_VOLUME", "+10%"),
            ("PIPER_MODEL", "en_US-amy-medium"),
            ("KOKORO_SPEED", "1.15"),
        ):
            with self.subTest(setting=setting), patch.dict(
                os.environ, {**base, setting: changed_value}, clear=True
            ):
                self.assertNotEqual(
                    tts._audio_cache_path("A documentary narration."), original
                )

    def test_explicit_kokoro_never_falls_back_to_paid_providers(self):
        with patch.dict(os.environ, {"TTS_PROVIDER": "kokoro"}, clear=False), \
             patch.object(tts, "_synthesize_kokoro") as kokoro, \
             patch.object(tts, "_synthesize_elevenlabs") as eleven, \
             patch.object(tts, "_synthesize_openai") as openai:
            result = tts.synthesize("A documentary narration.", self.out)
        self.assertEqual(result, self.out)
        kokoro.assert_called_once()
        eleven.assert_not_called()
        openai.assert_not_called()

    def test_explicit_kokoro_failure_does_not_try_paid_providers(self):
        with patch.dict(os.environ, {"TTS_PROVIDER": "kokoro"}, clear=False), \
             patch.object(tts, "_synthesize_kokoro", side_effect=RuntimeError("local model unavailable")), \
             patch.object(tts, "_synthesize_elevenlabs") as eleven, \
             patch.object(tts, "_synthesize_openai") as openai:
            with self.assertRaisesRegex(RuntimeError, "no paid TTS fallback"):
                tts.synthesize("A documentary narration.", self.out)
        eleven.assert_not_called()
        openai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
