import unittest
from pathlib import Path


class RemotionShotTimelineTests(unittest.TestCase):
    def test_each_selected_shot_runs_in_a_sequence_local_to_its_start(self):
        source = (
            Path(__file__).resolve().parents[1] / "JackPocketsVideo.tsx"
        ).read_text(encoding="utf-8")
        start = source.index("<Sequence\n          key={`shot-timeline-${activeShot.id}`}")
        end = source.index("</Sequence>", start)
        shot_sequence = source[start:end]
        self.assertIn(
            "from={Math.round((activeBeat.start + activeShot.start) * fps)}",
            shot_sequence,
        )
        self.assertIn(
            "durationInFrames={Math.max(1, Math.ceil((activeShot.end - activeShot.start) * fps))}",
            shot_sequence,
        )
        self.assertIn('<ShotView beat={activeBeat} shot={activeShot}', shot_sequence)

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
