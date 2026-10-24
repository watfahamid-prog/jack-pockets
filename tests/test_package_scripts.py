import json
import unittest
from pathlib import Path

class PackageScriptTests(unittest.TestCase):
    def test_render_script_has_explicit_mp4_output(self):
        root = Path(__file__).resolve().parents[1]
        scripts = json.loads((root / "package.json").read_text(encoding="utf-8"))["scripts"]
        tokens = scripts["render"].split()
        index = tokens.index("render")
        self.assertEqual(tokens[index + 1:index + 3], ["index.tsx", "JackPocketsVideo"])
        self.assertTrue(tokens[index + 3].endswith(".mp4"))

if __name__ == "__main__":
    unittest.main()
