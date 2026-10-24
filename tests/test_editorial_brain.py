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

    def test_validated_metadata_match_survives_provider_title_reduction(self):
        beat = {
            "id": "beat-provider-metadata",
            "start": 0,
            "end": 5,
            "title": "AS 7007 routing incident",
            "keywords": ["router network"],
            "narration": "The route was withdrawn.",
            "assets": [
                {
                    "id": "accepted-router-clip",
                    "kind": "video",
                    "title": "video 123",
                    "description": "",
                    "tags": [],
                    # These terms were matched against the provider's real
                    # metadata by the upstream strict relevance gate.
                    "relevance_terms": ["router", "network"],
                }
            ],
        }
        shots = build_shots(beat)["shots"]
        self.assertEqual(shots[0]["assetIds"], ["accepted-router-clip"])

    def test_shots_select_sentence_relevant_assets(self):
        beat = {
            "id": "beat-1", "start": 0, "end": 8,
            "narration": "Titanic wreck footage shows the ship. Titanic wreckage rests underwater.",
            "assets": [
                {"id": "ship", "kind": "video", "title": "Titanic wreck footage",
                 "description": "ship and wreck underwater", "tags": []},
                {"id": "underwater", "kind": "video", "title": "Underwater Titanic wreck site",
                 "description": "shipwreck below the surface", "tags": []},
            ],
        }
        result = build_shots(beat)
        self.assertEqual(len(result["shots"]), 2)
        self.assertEqual(result["shots"][0]["assetIds"], ["ship"])
        self.assertEqual(result["shots"][1]["assetIds"], ["underwater"])

    def test_connective_sentence_can_use_strongly_beat_relevant_video(self):
        beat = {
            "id": "beat-context", "start": 0, "end": 8,
            "title": "Rare emerald necklace auction",
            "keywords": ["emerald", "auction", "necklace"],
            "narration": "Rare emerald necklace sold at auction. That changed everything.",
            "assets": [
                {"id": "auction-video", "kind": "video",
                 "title": "Rare emerald necklace auction footage",
                 "description": "", "tags": []},
                {"id": "auction-room", "kind": "video",
                 "title": "Emerald necklace auction room",
                 "description": "Auction room with a rare jewel display", "tags": []},
            ],
        }
        shots = build_shots(beat)["shots"]
        self.assertEqual(len(shots), 2)
        self.assertEqual(shots[0]["assetIds"], ["auction-video"])
        self.assertEqual(shots[1]["assetIds"], ["auction-room"])

    def test_beat_context_uses_curated_keywords_after_the_title(self):
        beat = {
            "id": "beat-context-keywords", "start": 0, "end": 8,
            "title": "The Explanation and Apology",
            "keywords": [
                "nanog mailing list text email archive screenshot",
                "1990s desktop computer crt monitor",
                "tech documentation manual close up",
            ],
            "narration": "It was posted publicly. That became the record.",
            "assets": [
                {"id": "nanog", "kind": "video", "title": "NANOG mailing list email archive",
                 "description": "Early internet mailing list", "tags": []},
                {"id": "computer", "kind": "video", "title": "1990s desktop computer CRT monitor",
                 "description": "A vintage computer workstation", "tags": []},
            ],
        }
        shots = build_shots(beat)["shots"]
        self.assertEqual(shots[0]["assetIds"], ["nanog"])
        self.assertEqual(shots[1]["assetIds"], ["computer"])

    def test_single_clip_is_not_reused_on_adjacent_shots(self):
        beat = {
            "id": "beat-single-clip", "start": 0, "end": 8,
            "title": "Rare emerald necklace auction",
            "keywords": ["emerald necklace auction"],
            "narration": "Rare emerald necklace sold at auction. That changed everything.",
            "assets": [
                {"id": "auction-video", "kind": "video",
                 "title": "Rare emerald necklace auction footage",
                 "description": "", "tags": []},
            ],
        }
        shots = build_shots(beat)["shots"]
        self.assertEqual(shots[0]["assetIds"], ["auction-video"])
        self.assertEqual(shots[1]["assetIds"], [])

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

    def test_reference_style_value_label_is_short_and_specific(self):
        beat = {
            "id": "beat-4", "start": 0, "end": 6,
            "narration": "The total cost reached $50 billion.",
            "assets": [],
        }
        result = build_shots(beat)
        labels = [layer for layer in result["shots"][0]["layers"] if layer["kind"] == "label"]
        self.assertEqual([layer["text"] for layer in labels], ["TOTAL = $50 billion"])
        self.assertNotIn("$50 billion", result["shots"][0].get("assetIds", []))

    def test_late_alignment_spans_never_create_overlapping_shots(self):
        sentences_text = [f"Sentence token{i}." for i in range(10)]
        beat = {
            "id": "beat-late", "start": 10, "end": 14,
            "narration": " ".join(sentences_text),
            "assets": [],
        }
        words = []
        for i in range(10):
            start = 10.0 + i * 0.55
            words.extend([
                {"word": "Sentence", "start": start, "end": start + 0.2},
                {"word": f"token{i}", "start": start + 0.2, "end": start + 0.4},
            ])

        shots = build_shots(beat, aligned_words=words)["shots"]
        self.assertEqual(len(shots), 10)
        self.assertEqual(shots[0]["start"], 0.0)
        self.assertAlmostEqual(shots[-1]["end"], 4.0, places=3)
        for index, shot in enumerate(shots):
            self.assertGreater(shot["end"], shot["start"])
            self.assertGreaterEqual(shot["start"], 0.0)
            self.assertLessEqual(shot["end"], 4.0)
            if index:
                self.assertGreaterEqual(shot["start"], shots[index - 1]["end"])

    def test_unmatched_aligned_sentences_still_advance_timing(self):
        beat = {
            "id": "beat-5", "start": 10, "end": 20,
            "narration": "First sentence. Second sentence.",
            "assets": [],
        }
        words = [
            {"word": "First", "start": 10.0, "end": 10.4},
            {"word": "sentence", "start": 10.4, "end": 11.0},
            {"word": "unexpected", "start": 11.1, "end": 11.5},
            {"word": "words", "start": 11.5, "end": 12.0},
            {"word": "Second", "start": 12.0, "end": 12.5},
            {"word": "sentence", "start": 12.5, "end": 13.0},
        ]
        result = build_shots(beat, aligned_words=words)
        self.assertEqual(len(result["shots"]), 2)
        self.assertLess(result["shots"][0]["start"], result["shots"][1]["start"])
        self.assertGreater(result["shots"][1]["start"], 0)


if __name__ == "__main__":
    unittest.main()
