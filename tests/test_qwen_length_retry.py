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


class QwenLengthRetryTests(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_qwen_retries_a_short_plan_with_explicit_length_repair_prompt(self, openai_client):
        short = MagicMock()
        short.choices[0].message.content = json.dumps(make_plan(words_per_beat=30))
        long = MagicMock()
        long.choices[0].message.content = json.dumps(make_plan(words_per_beat=240))
        openai_client.return_value.chat.completions.create.side_effect = [short, long]

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
        self.assertEqual(openai_client.return_value.chat.completions.create.call_count, 2)
        retry_prompt = openai_client.return_value.chat.completions.create.call_args_list[1].kwargs["messages"][1]["content"]
        self.assertIn("LENGTH REPAIR", retry_prompt)
        self.assertIn("1,500 spoken words", retry_prompt)


if __name__ == "__main__":
    unittest.main()
