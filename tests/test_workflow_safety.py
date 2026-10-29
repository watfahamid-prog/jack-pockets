import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSafetyTests(unittest.TestCase):
    def test_invalid_evidence_gate_precedes_tts_and_media_acquisition(self):
        source = (ROOT / "generate.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")

        gate_line = next(
            node.lineno
            for node in ast.walk(main)
            if isinstance(node, ast.If)
            and any(
                isinstance(child, ast.Name) and child.id == "evidence_errors"
                for child in ast.walk(node.test)
            )
        )
        calls = {}
        for node in ast.walk(main):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.setdefault(node.func.id, node.lineno)

        for expensive_step in ("synthesize", "search_pexels_videos", "make_asset_plan", "get_music"):
            self.assertIn(expensive_step, calls, f"expected pipeline call {expensive_step}")
            self.assertLess(
                gate_line,
                calls[expensive_step],
                f"evidence gate must run before {expensive_step}",
            )

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
