import unittest

from editorial_brain import _asset_score, build_shots, sentences


class FootageMatchingTests(unittest.TestCase):
    def test_sentence_splitter_splits_normal_prose(self):
        self.assertEqual(
            sentences("Gold is rare. The auction followed. Why did it happen?"),
            ["Gold is rare.", "The auction followed.", "Why did it happen?"],
        )

    def test_metadata_relevance_beats_an_unrelated_unused_video(self):
        terms = {"titanic", "wreck"}
        relevant = {
            "id": "relevant", "kind": "video", "title": "Titanic wreck footage",
            "description": "", "tags": [],
        }
        unrelated = {
            "id": "fresh", "kind": "video", "title": "Mountain hiking",
            "description": "", "tags": [],
        }
        relevant_score = _asset_score(relevant, terms, "b-roll", reuse_count=1)
        unrelated_score = _asset_score(unrelated, terms, "b-roll", reuse_count=0)
        self.assertGreater(relevant_score, unrelated_score)

    def test_copied_search_query_does_not_fake_metadata_match(self):
        terms = {"titanic", "wreck"}
        asset = {
            "id": "weak", "kind": "video", "title": "Mountain hiking",
            "description": "", "tags": [],
            "query": "titanic wreck", "keywords": ["titanic", "wreck"],
        }
        self.assertLess(_asset_score(asset, terms, "b-roll"), 5)

    def test_shots_select_sentence_relevant_assets(self):
        beat = {
            "id": "beat-1", "start": 0, "end": 8,
            "narration": "Titanic wreck footage shows the ship. Mountain hiking is unrelated.",
            "assets": [
                {"id": "ship", "kind": "video", "title": "Titanic wreck footage",
                 "description": "ship underwater", "tags": []},
                {"id": "mountain", "kind": "video", "title": "Mountain hiking",
                 "description": "walking outdoors", "tags": []},
            ],
        }
        result = build_shots(beat)
        self.assertEqual(len(result["shots"]), 2)
        self.assertEqual(result["shots"][0]["assetIds"], ["ship"])
        self.assertEqual(result["shots"][1]["assetIds"], ["mountain"])

    def test_weak_assets_are_not_used_as_random_filler(self):
        beat = {
            "id": "beat-2", "start": 0, "end": 5,
            "narration": "The auction revealed a rare emerald necklace.",
            "assets": [
                {"id": "bridge", "kind": "video", "title": "City bridge at sunset",
                 "description": "traffic over a river", "tags": ["architecture"]},
            ],
        }
        result = build_shots(beat)
        self.assertEqual(result["shots"][0]["assetIds"], [])

    def test_relevant_repetition_is_discouraged_when_an_equal_match_exists(self):
        beat = {
            "id": "beat-3", "start": 0, "end": 10,
            "narration": "Gold bars fill the vault. Gold coins fill another vault.",
            "assets": [
                {"id": "bars", "kind": "video", "title": "Gold bars in a vault", "description": "", "tags": []},
                {"id": "coins", "kind": "video", "title": "Gold coins in a vault", "description": "", "tags": []},
            ],
        }
        result = build_shots(beat)
        ids = [shot["assetIds"][0] for shot in result["shots"]]
        self.assertEqual(ids, ["bars", "coins"])


if __name__ == "__main__":
    unittest.main()
