import json
import unittest
from unittest.mock import MagicMock, patch

import llm


def mock_ollama_response(content):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({
        "message": {"content": content, "thinking": ""},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 20,
        "eval_count": 100,
    }).encode("utf-8")
    return response


class QwenProviderTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_qwen_uses_native_local_ollama_endpoint_and_normalizes_plan(self, urlopen):
        plan = {
            "title": "Test topic",
            "beats": [
                {
                    "title": f"Beat {i}",
                    "narration": " ".join(
                        f"Beat {i} sentence {j} explains specific historical evidence for this topic in context."
                        for j in range(1, 21)
                    ),
                    "keywords": ["test topic", f"evidence {i}"],
                    "source_urls": ["https://example.com/source"],
                    "intensity": 0.5,
                }
                for i in range(1, 9)
            ],
        }
        urlopen.return_value = mock_ollama_response(json.dumps(plan))

        with patch.dict("os.environ", {
            "QWEN_BASE_URL": "http://localhost:11434/v1",
            "QWEN_MODEL": "qwen3:4b",
            "QWEN_API_KEY": "",
        }, clear=False):
            result = llm._qwen("Test topic", [{"url": "https://example.com/source", "title": "Source"}])

        self.assertEqual(result["title"], "Test topic")
        self.assertEqual(len(result["beats"]), 8)
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/chat")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "qwen3:4b")
        self.assertFalse(payload["think"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["num_ctx"], 16384)
        self.assertEqual([message["role"] for message in payload["messages"]], ["system", "user"])
        self.assertNotIn("<think>", payload["messages"][-1]["content"])

    @patch("urllib.request.urlopen")
    def test_qwen_includes_ollama_http_error_body_in_diagnostic(self, urlopen):
        import io
        from urllib.error import HTTPError

        urlopen.side_effect = HTTPError(
            "http://localhost:11434/api/chat",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"error":"invalid chat template"}'),
        )
        with patch.dict("os.environ", {
            "QWEN_BASE_URL": "http://localhost:11434/v1",
            "QWEN_MODEL": "qwen3:4b-instruct",
        }, clear=False):
            with self.assertRaisesRegex(RuntimeError, "HTTP 400.*invalid chat template"):
                llm._qwen("Test topic", [{"url": "https://example.com/source", "title": "Source"}])


if __name__ == "__main__":
    unittest.main()
