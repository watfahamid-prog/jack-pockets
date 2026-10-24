import tempfile
import unittest
from pathlib import Path

from harness2.record_run import render_memory, summarize, update_ledger


class Harness2RunFeedbackTests(unittest.TestCase):
    def test_detects_quality_gate_failure(self):
        text = "QUALITY GATE FAILED:\nfootage gate: only 2 distinct real video clips selected; need at least 6\nstatic-image gate: photos fill 20% of shots; maximum is 15%\n"
        result = summarize(text, None)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["observations"]), 2)

    def test_marks_render_only_when_final_qc_is_logged(self):
        self.assertEqual(summarize("FINAL QC PASSED: out/test.mp4", None)["status"], "passed")
        self.assertEqual(summarize("READY: manifest.json", None)["status"], "incomplete")

    def test_ledger_persists_runs_and_surfaces_repeated_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            update_ledger(path, {"run_id": "1", "observations": ["no relevant moving video"]})
            ledger = update_ledger(path, {"run_id": "2", "observations": ["no relevant moving video"]})
            self.assertEqual(len(ledger["runs"]), 2)
            self.assertEqual(ledger["runs"][-1]["recurring_observations"]["no relevant moving video"], 2)
            self.assertIn("Observed 2 times", render_memory(ledger))


if __name__ == "__main__":
    unittest.main()
