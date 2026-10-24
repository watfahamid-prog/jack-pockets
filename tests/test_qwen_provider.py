import unittest
from unittest.mock import MagicMock, patch

import llm


class QwenProviderTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_qwen_uses_local_openai_compatible_endpoint_and_normalizes_plan(self, openai_client):
        plan = {
            "title": "Test topic",
            "beats": [
                {
                    "title": f"Beat {i}",
                    "narration": (" ".join(f"Beat {i} sentence {j} explains specific historical evidence for this topic in context." for j in range(1, 21))),
                    "keywords": ["test topic", f"evidence {i}"],
                    "source_urls": ["https://example.com/source"],
                    "intensity": 0.5,
                }
                for i in range(1, 9)
            ],
        }
        response = MagicMock()
        response.choices[0].message.content = __import__("json").dumps(plan)
        openai_client.return_value.chat.completions.create.return_value = response

        with patch.dict("os.environ", {
            "QWEN_BASE_URL": "http://localhost:11434/v1",
            "QWEN_MODEL": "qwen3:4b",
            "QWEN_API_KEY": "",
        }, clear=False):
            result = llm._qwen("Test topic", [{"url": "https://example.com/source", "title": "Source"}])

        self.assertEqual(result["title"], "Test topic")
        self.assertEqual(len(result["beats"]), 8)
        openai_client.assert_called_once()
        kwargs = openai_client.call_args.kwargs
        self.assertEqual(kwargs["base_url"], "http://localhost:11434/v1")
        self.assertEqual(kwargs["api_key"], "ollama")
        self.assertEqual(openai_client.return_value.chat.completions.create.call_args.kwargs["model"], "qwen3:4b")

    @patch("openai.OpenAI")
    def test_qwen_provider_does_not_require_cloud_api_key(self, openai_client):
        plan = {
            "title": "Local test",
            "beats": [
                {
                    "title": f"Beat {i}",
                    "narration": (" ".join(f"Beat {i} sentence {j} explains local Qwen testing and specific source evidence in context." for j in range(1, 21))),
                    "keywords": ["local Qwen", f"source {i}"],
                    "source_urls": ["https://example.com/source"],
                }
                for i in range(1, 9)
            ],
        }
        response = MagicMock()
        response.choices[0].message.content = __import__("json").dumps(plan)
        openai_client.return_value.chat.completions.create.return_value = response
        with patch.dict("os.environ", {"QWEN_API_KEY": "", "QWEN_BASE_URL": "http://localhost:11434/v1"}, clear=False):
            result = llm._qwen("Local test", [])
        self.assertGreaterEqual(sum(len(b["narration"].split()) for b in result["beats"]), llm.MIN_NARRATION_WORDS)


if __name__ == "__main__":
    unittest.main()
