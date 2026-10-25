import json
import unittest
from unittest.mock import MagicMock, patch

import llm


def make_plan(words_per_beat=30):
    beats = []
    for i in range(1, 9):
        narration = " ".join(
            f"Beat {i} sentence {j} explains specific historical evidence and context for this documentary topic."
            for j in range(1, max(2, words_per_beat // 11) + 1)
        )
        beats.append({
            "title": f"Beat {i}",
            "narration": narration,
            "keywords": [f"topic {i}", f"evidence {i}"],
            "source_urls": ["https://example.com/source"],
            "intensity": 0.5,
        })
    return {"title": "Test topic", "beats": beats}


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


class QwenLengthRetryTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_qwen_retries_a_short_plan_with_explicit_length_repair_prompt(self, urlopen):
        urlopen.side_effect = [
            mock_ollama_response(json.dumps(make_plan(words_per_beat=30))),
            mock_ollama_response(json.dumps(make_plan(words_per_beat=240))),
        ]

        with patch.dict("os.environ", {
            "QWEN_BASE_URL": "http://localhost:11434/v1",
            "QWEN_MODEL": "qwen3:4b",
            "QWEN_API_KEY": "ollama",
            "QWEN_MAX_TOKENS": "9000",
        }, clear=False):
            result = llm._qwen("Test topic", [{"url": "https://example.com/source", "title": "Source"}])

        self.assertGreaterEqual(
            sum(len(beat["narration"].split()) for beat in result["beats"]),
            llm.MIN_NARRATION_WORDS,
        )
        self.assertEqual(urlopen.call_count, 2)
        retry_payload = json.loads(urlopen.call_args_list[1].args[0].data.decode("utf-8"))
        retry_prompt = retry_payload["messages"][1]["content"]
        self.assertIn("LENGTH REPAIR", retry_prompt)
        self.assertIn("1,500 spoken words", retry_prompt)


if __name__ == "__main__":
    unittest.main()
