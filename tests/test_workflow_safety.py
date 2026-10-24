from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSafetyTests(unittest.TestCase):
    def test_generation_topic_is_passed_through_environment(self):
        workflow = (ROOT / ".github" / "workflows" / "generate-video.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("DOCUMENTARY_TOPIC: ${{ inputs.topic }}", workflow)
        self.assertIn('run: python generate.py --topic "$DOCUMENTARY_TOPIC" --assets-per-beat 2', workflow)
        self.assertNotIn('run: python generate.py --topic "${{ inputs.topic }}"', workflow)


if __name__ == "__main__":
    unittest.main()
