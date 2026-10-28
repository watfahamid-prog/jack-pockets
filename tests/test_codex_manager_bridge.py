import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
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

    def test_isolated_worktree_keeps_original_checkout_and_untracked_file_safe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            task_path = root / "bridge" / "worktrees" / "issue-123"
            repo.mkdir()
            subprocess.run(
                ["git", "init", "--initial-branch=main", str(repo)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Bridge Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "bridge-test@example.invalid"], check=True)
            (repo / "README.md").write_text("tracked baseline\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"],
                check=True,
            )
            scratch = repo / "local_agent_test.py"
            scratch.write_text("keep this local\n", encoding="utf-8")

            bridge.create_isolated_worktree(repo, "codex/test-issue-123", task_path)

            branch = subprocess.run(
                ["git", "-C", str(repo), "branch", "--show-current"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            task_branch = subprocess.run(
                ["git", "-C", str(task_path), "branch", "--show-current"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            self.assertEqual(branch, "main")
            self.assertEqual(task_branch, "codex/test-issue-123")
            self.assertEqual(scratch.read_text(encoding="utf-8"), "keep this local\n")
            self.assertFalse((task_path / "local_agent_test.py").exists())
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "remove", "--force", str(task_path)],
                check=True, capture_output=True, text=True,
            )

    def test_cli_bridge_is_disabled_without_explicit_opt_in(self):
        with patch.object(sys, "argv", ["codex_manager_bridge.py"]):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(bridge.main(), 2)
        self.assertIn("disabled by default", stderr.getvalue())
        self.assertIn("Codex Desktop", stderr.getvalue())

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
        comments = [{
            "user": {"login": "watfahamid-prog"},
            "body": "started <!-- codex-manager-bridge: started -->",
        }]
        self.assertTrue(bridge.issue_is_processed(comments))
        self.assertFalse(bridge.issue_is_processed([{"body": "ordinary comment"}]))

    def test_other_users_cannot_spoof_processed_marker(self):
        comments = [{
            "user": {"login": "someone-else"},
            "body": "<!-- codex-manager-bridge: completed -->",
        }]
        self.assertFalse(bridge.issue_is_processed(comments))

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
        for path in (".env", ".env.production", "production.env", "secrets/token.txt", "credentials.json", "client.pem", ".npmrc"):
            with self.subTest(path=path):
                self.assertTrue(bridge.is_sensitive_path(path))
        for path in (".env.example", "assets.py", "tests/test_relevance.py"):
            with self.subTest(path=path):
                self.assertFalse(bridge.is_sensitive_path(path))

    def test_sensitive_changes_cannot_be_staged(self):
        with self.assertRaises(bridge.BridgeError):
            bridge.paths_to_stage([("??", ".env.production")])

    def test_generated_media_and_cache_artifacts_cannot_be_staged(self):
        for path in (
            "out/final.mp4",
            "public/runs/final.mp4",
            "downloads/archive.zip",
            "models/weights.onnx",
            "node_modules/some-package/index.js",
            "cache/run.log",
            "__pycache__/module.pyc",
            "assets/generated.png",
            "captions/episode.srt",
        ):
            with self.subTest(path=path):
                self.assertTrue(bridge.is_disallowed_artifact_path(path))
                with self.assertRaises(bridge.BridgeError):
                    bridge.paths_to_stage([("??", path)])

    def test_public_summary_scrubs_tokens_and_windows_paths(self):
        source = (
            r"failed at C:\Users\asus\Projects\jack-pockets\out\clip.mp4 "
            "with ghp_ABCDEFGHIJKLMNOPQRSTUVWX and api_key=very-secret-token-value "
            "and PEXELS_API_KEY=abcdefgh1234567890"
        )
        redacted = bridge.scrub_public_text(source)
        self.assertNotIn("ghp_ABCDEFGHIJKLMNOPQRSTUVWX", redacted)
        self.assertNotIn("very-secret-token-value", redacted)
        self.assertNotIn("abcdefgh1234567890", redacted)
        self.assertNotIn(r"C:\Users\asus", redacted)
        self.assertIn("[REDACTED", redacted)


if __name__ == "__main__":
    unittest.main()
