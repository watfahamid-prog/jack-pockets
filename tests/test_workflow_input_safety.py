import unittest
from pathlib import Path


class DocumentaryWorkflowInputSafetyTests(unittest.TestCase):
    def test_manual_topic_uses_random_delimited_environment_value(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "generate-video.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('delimiter="$(openssl rand -hex 24)"', workflow)
        self.assertIn("printf 'DOCUMENTARY_TOPIC<<%s\\n' \"$delimiter\"", workflow)
        self.assertIn('} >> "$GITHUB_ENV"', workflow)

    def test_manual_topic_is_not_written_as_an_unescaped_single_line(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "generate-video.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn('echo "DOCUMENTARY_TOPIC=$INPUT_TOPIC" >> "$GITHUB_ENV"', workflow)


if __name__ == "__main__":
    unittest.main()
