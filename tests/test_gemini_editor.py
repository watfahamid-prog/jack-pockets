import unittest
from unittest.mock import patch

import gemini_editor


class GeminiEditorProviderTests(unittest.TestCase):
    @patch("gemini_editor.genai.Client")
    def test_missing_api_key_skips_gemini(self, client):
        beat = {"title": "Test beat", "narration": "A test beat.", "keywords": ["local", "test"]}
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
            result = gemini_editor.refine_beat(beat)
        self.assertIs(result, beat)
        client.assert_not_called()

    @patch("gemini_editor.genai.Client")
    def test_configured_api_key_invokes_gemini(self, client):
        beat = {"title": "Test beat", "narration": "A test beat.", "keywords": ["local", "test"]}
        client.return_value.models.generate_content.return_value.text = '{"sentences": []}'
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_EDITOR_MODEL": "test-model"}, clear=False):
            gemini_editor.refine_beat(beat)
        client.assert_called_once_with(api_key="test-key")
        client.return_value.models.generate_content.assert_called_once()


if __name__ == "__main__":
    unittest.main()
