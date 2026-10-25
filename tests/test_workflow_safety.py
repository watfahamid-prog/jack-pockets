from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSafetyTests(unittest.TestCase):
    def test_generation_topic_is_passed_through_environment(self):
        workflow = (ROOT / ".github" / "workflows" / "generate-video.yml").read_text(encoding="utf-8")
        self.assertIn('DOCUMENTARY_TOPIC: "The 1997 AS 7007 Internet Routing Incident: How One Router Disrupted Internet Traffic"', workflow)
        self.assertIn("INPUT_TOPIC:", workflow)
        self.assertIn('python generate.py --topic "$DOCUMENTARY_TOPIC" --assets-per-beat 2 2>&1 | tee "$RUNNER_TEMP/jack-pockets-generate.log"', workflow)
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("Record Harness² run feedback", workflow)
        self.assertIn('JACKPOCKETS_VIDEO_QC: "1"', workflow)
        self.assertIn("public/runs/**/video-qc.json", workflow)
        self.assertIn("ANTHROPIC_MODEL:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("ollama", workflow.lower())
        self.assertNotIn("full-free-acceptance", workflow)
        configured_run = workflow.split("Generate 1080p30 documentary with configured providers", 1)[1]
        for paid_key in ("GEMINI_API_KEY:", "OPENAI_API_KEY:", "ANTHROPIC_API_KEY:", "ELEVENLABS_API_KEY:", "PERPLEXITY_API_KEY:", "TAVILY_API_KEY:", "MUSIC_URL:"):
            self.assertIn(paid_key, configured_run)


if __name__ == "__main__":
    unittest.main()
