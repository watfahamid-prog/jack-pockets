import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_manager_bridge as bridge


class CodexManagerBridgeContractTests(unittest.TestCase):
    def make_issue(self, **overrides):
        issue = {
            "number": 123,
            "state": "open",
            "title": "[CODEX-TASK] Fix footage matching regression",
            "body": bridge.TASK_MARKER + "\n\n## Goal\nFix the observed matching regression.",
            "user": {"login": "watfahamid-prog"},
            "html_url": "https://github.com/watfahamid-prog/jack-pockets/issues/123",
        }
        issue.update(overrides)
        return issue

    def test_accepts_only_marked_owner_authored_task(self):
        self.assertTrue(bridge.issue_is_eligible(self.make_issue()))

    def test_rejects_other_authors(self):
        issue = self.make_issue(user={"login": "someone-else"})
        self.assertFalse(bridge.issue_is_eligible(issue))

    def test_rejects_pull_requests_as_tasks(self):
        issue = self.make_issue(pull_request={"url": "https://api.github.com/pulls/123"})
        self.assertFalse(bridge.issue_is_eligible(issue))

    def test_rejects_unmarked_or_wrong_title(self):
        self.assertFalse(bridge.issue_is_eligible(self.make_issue(body="ordinary issue")))
        self.assertFalse(bridge.issue_is_eligible(self.make_issue(title="Fix anything")))

    def test_rejects_closed_and_oversized_tasks(self):
        self.assertFalse(bridge.issue_is_eligible(self.make_issue(state="closed")))
        long_body = bridge.TASK_MARKER + ("x" * (bridge.MAX_TASK_BODY_CHARS + 1))
        self.assertFalse(bridge.issue_is_eligible(self.make_issue(body=long_body)))

    def test_processed_marker_stops_repeated_execution(self):
        comments = [{"body": "started <!-- codex-manager-bridge: started -->"}]
        self.assertTrue(bridge.issue_is_processed(comments))
        self.assertFalse(bridge.issue_is_processed([{"body": "ordinary comment"}]))

    def test_porcelain_parser_preserves_paths(self):
        output = "?? local_agent_test.py\0 M assets.py\0A  tests/test_new_case.py\0"
        self.assertEqual(
            bridge.parse_porcelain_z(output),
            [("??", "local_agent_test.py"), (" M", "assets.py"), ("A ", "tests/test_new_case.py")],
        )

    def test_existing_untracked_test_is_never_staged(self):
        entries = [
            ("??", "local_agent_test.py"),
            (" M", "assets.py"),
            ("??", "tests/test_new_case.py"),
        ]
        self.assertEqual(
            bridge.paths_to_stage(entries),
            ["assets.py", "tests/test_new_case.py"],
        )

    def test_sensitive_paths_are_rejected(self):
        for path in (".env", ".env.production", "secrets/token.txt", "credentials.json", "client.pem", ".npmrc"):
            with self.subTest(path=path):
                self.assertTrue(bridge.is_sensitive_path(path))
        for path in (".env.example", "assets.py", "tests/test_relevance.py"):
            with self.subTest(path=path):
                self.assertFalse(bridge.is_sensitive_path(path))

    def test_sensitive_changes_cannot_be_staged(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.paths_to_stage([("??", ".env.production")])


if __name__ == "__main__":
    unittest.main()
