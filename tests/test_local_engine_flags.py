from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tts


class LocalTtsSelectionTests(unittest.TestCase):
    def test_explicit_kokoro_does_not_try_paid_providers(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "narration.mp3"
            with patch.dict(os.environ, {
                "TTS_PROVIDER": "kokoro",
                "JACKPOCKETS_DISABLE_CACHE": "1",
                "ELEVENLABS_API_KEY": "test-key",
                "ELEVENLABS_VOICE_ID": "test-voice",
                "OPENAI_API_KEY": "test-key",
            }, clear=False), patch.object(tts, "_synthesize_kokoro") as kokoro, patch.object(
                tts, "_synthesize_elevenlabs"
            ) as eleven, patch.object(tts, "_synthesize_openai") as openai, patch.object(
                tts, "_save_audio_cache"
            ):
                tts.synthesize("A short test narration.", output)
                kokoro.assert_called_once()
                eleven.assert_not_called()
                openai.assert_not_called()

    def test_unknown_provider_fails_clearly(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {
                "TTS_PROVIDER": "not-a-provider",
                "JACKPOCKETS_DISABLE_CACHE": "1",
            }, clear=False):
                with self.assertRaisesRegex(ValueError, "TTS_PROVIDER"):
                    tts.synthesize("A short test narration.", Path(temp) / "narration.mp3")


if __name__ == "__main__":
    unittest.main()
