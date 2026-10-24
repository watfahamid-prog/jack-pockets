import tempfile
import unittest
from pathlib import Path

from harness2.propose_improvements import build_proposals, render_candidate_memory


class Harness2ImprovementProposalTests(unittest.TestCase):
    def test_repeated_observations_create_proposal_not_automatic_change(self):
        ledger = {"runs": [
            {"observations": ["no relevant moving video"]},
            {"observations": ["no relevant moving video"]},
        ]}
        result = build_proposals(ledger)
        self.assertEqual(result["proposals"][0]["id"], "footage-relevance")
        self.assertEqual(result["proposals"][0]["status"], "proposed_not_adopted")
        self.assertIn("No production code", result["proposals"][0]["safety"])

    def test_repeated_real_motion_gate_failure_creates_quality_gate_proposal(self):
        observation = "motion gate: shot has no visual asset: beat-8-shot-8"
        result = build_proposals({"runs": [
            {"observations": [observation]},
            {"observations": [observation]},
        ]})
        quality = next(
            (item for item in result["proposals"] if item["id"] == "quality-gate"),
            None,
        )
        self.assertIsNotNone(quality)
        self.assertEqual(quality["evidence_count"], 2)
        self.assertEqual(quality["status"], "proposed_not_adopted")

    def test_single_observation_does_not_create_proposal(self):
        result = build_proposals({"runs": [{"observations": ["provider search failed"]}]})
        self.assertEqual(result["proposals"], [])

    def test_memory_explains_candidate_is_not_adopted(self):
        proposals = build_proposals({"runs": [
            {"observations": ["static-image gate failed"]},
            {"observations": ["static-image gate failed"]},
        ]})
        memory = render_candidate_memory("# Existing memory\n", proposals)
        self.assertIn("Candidate experiments (not adopted)", memory)
        self.assertIn("production behavior unchanged", memory)


if __name__ == "__main__":
    unittest.main()
