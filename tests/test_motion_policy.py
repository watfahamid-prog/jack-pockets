import unittest

from editorial_brain import build_shots


class MotionPolicyTests(unittest.TestCase):
    def test_broll_prefers_video_and_does_not_fall_back_to_photo(self):
        beat = {
            "id": "beat-motion",
            "start": 0,
            "end": 8,
            "narration": "The factory produces steel every day.",
            "assets": [
                {
                    "id": "photo-factory",
                    "kind": "photo",
                    "role": "b-roll",
                    "title": "factory steel production",
                    "description": "factory steel production",
                    "tags": ["factory", "steel", "production"],
                },
                {
                    "id": "video-factory",
                    "kind": "video",
                    "role": "b-roll",
                    "title": "factory steel production",
                    "description": "factory steel production",
                    "tags": ["factory", "steel", "production"],
                    "source_url": "https://example.com/video",
                    "license": "Test",
                },
            ],
        }
        result = build_shots(beat)
        self.assertEqual(result["shots"][0]["assetIds"], ["video-factory"])

    def test_broll_does_not_turn_into_photo_slideshow_when_only_photo_exists(self):
        beat = {
            "id": "beat-static",
            "start": 0,
            "end": 8,
            "narration": "The factory produces steel every day.",
            "assets": [
                {
                    "id": "photo-factory",
                    "kind": "photo",
                    "role": "b-roll",
                    "title": "factory steel production",
                    "description": "factory steel production",
                    "tags": ["factory", "steel", "production"],
                },
            ],
        }
        result = build_shots(beat)
        self.assertEqual(result["shots"][0]["assetIds"], [])

    def test_chart_role_can_use_static_evidence(self):
        beat = {
            "id": "beat-chart",
            "start": 0,
            "end": 8,
            "narration": "The chart shows the total cost reached 100 billion.",
            "editorial": {"sentences": [{"visual_role": "chart"}]},
            "assets": [
                {
                    "id": "generated-chart",
                    "kind": "generated",
                    "role": "chart",
                    "title": "total cost chart",
                    "description": "total cost chart",
                    "tags": ["cost", "chart", "total"],
                },
            ],
        }
        result = build_shots(beat)
        self.assertEqual(result["shots"][0]["assetIds"], ["generated-chart"])


if __name__ == "__main__":
    unittest.main()
