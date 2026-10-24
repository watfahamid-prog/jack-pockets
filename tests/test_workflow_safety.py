from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSafetyTests(unittest.TestCase):
    def test_generation_topic_is_passed_through_environment(self):
        workflow = (ROOT / ".github" / "workflows" / "generate-video.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("DOCUMENTARY_TOPIC: ${{ inputs.topic }}", workflow)
        self.assertIn('python generate.py --topic "$DOCUMENTARY_TOPIC" --assets-per-beat 2 2>&1 | tee "$RUNNER_TEMP/jack-pockets-generate.log"', workflow)
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("Record Harness² run feedback", workflow)
        self.assertIn('JACKPOCKETS_VIDEO_QC: "1"', workflow)
        self.assertIn("public/runs/**/video-qc.json", workflow)
        self.assertIn("ANTHROPIC_MODEL: ${{ secrets.ANTHROPIC_MODEL }}", workflow)
        self.assertNotIn('run: python generate.py --topic "${{ inputs.topic }}"', workflow)


if __name__ == "__main__":
    unittest.main()
