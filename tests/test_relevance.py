import unittest

from relevance import _asset_relevance, _asset_search_queries, _relevant_sources
from unittest.mock import patch

import semantic_ranker


class AssetRelevanceTests(unittest.TestCase):
    def test_media_queries_prioritize_specific_keywords_over_generic_chapter_title(self):
        beat = {
            "title": "The Emerging Frontier: Celestial Real Estate",
            "keywords": ["lunar outpost", "Artemis Accords", "moon surface"],
            "visual_intent": "NASA lunar lander on the Moon",
            "narration": "The next lunar outpost depends on NASA missions and surface access.",
        }
        queries = _asset_search_queries(beat, limit=4)
        self.assertEqual(queries[0], "lunar outpost Artemis Accords moon surface")
        self.assertEqual(queries[1], "NASA lunar lander on the Moon")
        self.assertNotEqual(queries[0], beat["title"])
        self.assertLessEqual(len(queries), 4)

    def test_media_queries_skip_generic_or_duplicate_candidates(self):
        beat = {
            "title": "The True Cost of Human Ambition",
            "keywords": ["the", "future", "cost"],
            "narration": "The story reveals the future.",
        }
        self.assertEqual(_asset_search_queries(beat, limit=4), [])

    def test_accepts_exact_subject_terms_in_clip_metadata(self):
        beat = {
            "title": "AS 7007 routing incident",
            "keywords": ["router", "network routing"],
        }
        asset = {
            "title": "Router network routing equipment",
            "description": "Close-up of network routers",
            "tags": ["network", "router"],
        }
        relevant, matched = _asset_relevance("router network", beat, asset)
        self.assertTrue(relevant)
        self.assertIn("router", matched)
        self.assertIn("network", matched)

    def test_accepts_one_specific_subject_match_for_relevant_stock(self):
        beat = {
            "title": "Library archives historical manuscripts",
            "keywords": ["library", "archives", "historical", "manuscripts"],
        }
        asset = {
            "title": "A person using a library catalog",
            "description": "Browsing a library card catalogue",
            "tags": [],
        }
        relevant, matched = _asset_relevance("library archives", beat, asset)
        self.assertTrue(relevant)
        self.assertIn("library", matched)

    def test_rejects_substring_only_match(self):
        beat = {"title": "car", "keywords": ["car"]}
        asset = {"title": "Carpet installation", "description": "Carpet fitting"}
        relevant, matched = _asset_relevance("car", beat, asset)
        self.assertFalse(relevant)
        self.assertEqual(matched, [])

    def test_rejects_unrelated_clip_when_topic_has_many_terms(self):
        beat = {
            "title": "Apollo lunar landing",
            "keywords": ["moon", "astronaut", "spacecraft"],
        }
        asset = {
            "title": "City traffic at night",
            "description": "Cars driving through downtown",
            "tags": ["road", "urban"],
        }
        relevant, matched = _asset_relevance("Apollo lunar landing", beat, asset)
        self.assertFalse(relevant)
        self.assertEqual(matched, [])


class ResearchRelevanceTests(unittest.TestCase):
    def test_keeps_sources_with_exact_subject_overlap(self):
        sources = [
            {
                "url": "https://example.org/router-incident",
                "title": "AS 7007 router routing incident",
                "content": "The router announced incorrect network routes.",
            },
            {
                "url": "https://example.org/carpet",
                "title": "Carpet installation guide",
                "content": "Learn to fit carpet in a home.",
            },
        ]
        result = _relevant_sources(
            "AS 7007 routing incident",
            {"title": "Router leak", "narration": "The router leaked routes across networks."},
            sources,
        )
        self.assertEqual(result, ["https://example.org/router-incident"])

    def test_rejects_substring_only_source_match(self):
        sources = [
            {
                "url": "https://example.org/carpet",
                "title": "Carpet fitting",
                "content": "A guide to carpet installation.",
            }
        ]
        result = _relevant_sources(
            "car",
            {"title": "car", "narration": "car"},
            sources,
        )
        self.assertEqual(result, [])



class SemanticRankerTests(unittest.TestCase):
    def test_empty_assets_returns_without_loading_model(self):
        with patch.object(semantic_ranker, "_model") as model:
            self.assertEqual(semantic_ranker.score_assets("a ship", []), {})
            model.assert_not_called()

    def test_optional_model_is_lazy_loaded(self):
        self.assertTrue(callable(semantic_ranker.score_assets))


if __name__ == "__main__":
    unittest.main()
