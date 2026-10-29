import re
import unittest
from pathlib import Path


class RemotionShotTimelineTests(unittest.TestCase):
    def test_each_selected_shot_runs_in_a_sequence_local_to_its_start(self):
        source = (
            Path(__file__).resolve().parents[1] / "JackPocketsVideo.tsx"
        ).read_text(encoding="utf-8")
        pattern = re.compile(
            r"<Sequence\\s+"
            r"key=\\{\x60shot-timeline-\\$\\{activeShot\\.id\\}\x60\\}\\s+"
            r"from=\\{Math\\.round\\(\\(activeBeat\\.start \\+ activeShot\\.start\\) \\* fps\\)\\}\\s+"
            r"durationInFrames=\\{Math\\.max\\(1, Math\\.ceil\\(\\(activeShot\\.end - activeShot\\.start\\) \\* fps\\)\\)\\}\\s+"
            r'layout="none"\\s*>\\s*<ShotView',
            re.MULTILINE,
        )
        self.assertRegex(source, pattern)

    def test_shot_timeline_has_finite_positive_duration(self):
        source = (
            Path(__file__).resolve().parents[1] / "JackPocketsVideo.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "durationInFrames={Math.max(1, Math.ceil((activeShot.end - activeShot.start) * fps))}",
            source,
        )


if __name__ == "__main__":
    unittest.main()
