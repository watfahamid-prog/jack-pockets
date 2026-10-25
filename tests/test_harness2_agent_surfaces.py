from pathlib import Path
import tempfile
import unittest

from harness2.render_native_harness import MANIFEST, render


class AgentSurfaceTests(unittest.TestCase):
    def test_renderer_writes_both_agent_instruction_files_and_skills(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "native"
            memory = Path(temporary) / "memory.md"
            memory.write_text("# Test memory\n\nOverlay passed from test.\n", encoding="utf-8")

            render(MANIFEST, output, memory)

            codex = (output / "AGENTS.md").read_text(encoding="utf-8")
            claude = (output / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("Overlay passed from test.", codex)
            self.assertIn("Overlay passed from test.", claude)
            self.assertIn("quality gates", codex.lower())
            self.assertIn("quality gates", claude.lower())
            self.assertTrue((output / ".agents" / "skills").is_dir())
            self.assertTrue((output / ".claude" / "skills").is_dir())
            self.assertTrue(list((output / ".agents" / "skills").glob("*/SKILL.md")))
            self.assertTrue(list((output / ".claude" / "skills").glob("*/SKILL.md")))

    def test_renderer_rejects_missing_memory_overlay(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                render(MANIFEST, Path(temporary) / "native", Path(temporary) / "missing.md")


if __name__ == "__main__":
    unittest.main()
