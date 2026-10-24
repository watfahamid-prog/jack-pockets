from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSafetyTests(unittest.TestCase):
    def test_generation_topic_is_passed_through_environment_with_safe_fallback(self):
        workflow = (ROOT / ".github" / "workflows" / "generate-video.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("DOCUMENTARY_TOPIC: ${{ inputs.topic ||", workflow)
        self.assertIn("The 1997 AS 7007 Internet Routing Incident", workflow)
        self.assertIn('python generate.py --topic "$DOCUMENTARY_TOPIC" --assets-per-beat 2 2>&1 | tee "$RUNNER_TEMP/jack-pockets-generate.log"', workflow)
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("Record Harness² run feedback", workflow)
        self.assertNotIn('run: python generate.py --topic "${{ inputs.topic }}"', workflow)


if __name__ == "__main__":
    unittest.main()
