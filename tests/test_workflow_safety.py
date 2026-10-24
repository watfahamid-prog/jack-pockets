from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSafetyTests(unittest.TestCase):
    def test_generation_topic_is_passed_through_environment(self):
        workflow = (ROOT / ".github" / "workflows" / "generate-video.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('DOCUMENTARY_TOPIC: "The 1997 AS 7007 Internet Routing Incident: How One Router Disrupted Internet Traffic"', workflow)
        self.assertIn("INPUT_TOPIC: ${{ inputs.topic }}", workflow)
        self.assertIn('python generate.py --topic "$DOCUMENTARY_TOPIC" --assets-per-beat 2 2>&1 | tee "$RUNNER_TEMP/jack-pockets-generate.log"', workflow)
        self.assertIn("set -o pipefail", workflow)
        self.assertIn("Record Harness² run feedback", workflow)
        self.assertIn('JACKPOCKETS_VIDEO_QC: "1"', workflow)
        self.assertIn("public/runs/**/video-qc.json", workflow)
        self.assertIn("ANTHROPIC_MODEL: ${{ secrets.ANTHROPIC_MODEL }}", workflow)
        free_run = workflow.split("Generate free 1080p30 documentary with local Qwen", 1)[1].split("Generate 1080p30 documentary with configured providers", 1)[0]
        self.assertIn("branches: [full-free-acceptance]", workflow)
        self.assertIn("LLM_PROVIDER: qwen", free_run)
        self.assertIn("TTS_PROVIDER: edge", free_run)
        for paid_key in ("GEMINI_API_KEY:", "OPENAI_API_KEY:", "ANTHROPIC_API_KEY:", "ELEVENLABS_API_KEY:", "PERPLEXITY_API_KEY:", "TAVILY_API_KEY:", "MUSIC_URL:"):
            self.assertNotIn(paid_key, free_run)
        self.assertNotIn('run: python generate.py --topic "${{ inputs.topic }}"', workflow)


if __name__ == "__main__":
    unittest.main()
