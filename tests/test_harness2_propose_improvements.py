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
