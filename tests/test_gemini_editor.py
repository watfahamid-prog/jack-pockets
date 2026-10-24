import unittest
from unittest.mock import patch

import gemini_editor


class GeminiEditorProviderTests(unittest.TestCase):
    @patch("gemini_editor.genai.Client")
    def test_qwen_mode_skips_gemini_even_when_key_is_configured(self, client):
        beat = {"title": "Local Qwen beat", "narration": "A test beat.", "keywords": ["local", "test"]}

        with patch.dict("os.environ", {
            "LLM_PROVIDER": "qwen",
            "GEMINI_API_KEY": "configured-but-must-not-be-used",
        }, clear=False):
            result = gemini_editor.refine_beat(beat)

        self.assertIs(result, beat)
        client.assert_not_called()

    @patch("gemini_editor.genai.Client")
    def test_explicit_opt_in_allows_gemini_editor_with_qwen(self, client):
        beat = {"title": "Opt-in beat", "narration": "A test beat.", "keywords": ["local", "test"]}
        with patch.dict("os.environ", {
            "LLM_PROVIDER": "qwen",
            "GEMINI_API_KEY": "explicit-opt-in-key",
            "JACKPOCKETS_ALLOW_GEMINI_EDITOR_WITH_QWEN": "1",
        }, clear=False):
            gemini_editor.refine_beat(beat)

        client.assert_called_once_with(api_key="explicit-opt-in-key")


if __name__ == "__main__":
    unittest.main()
