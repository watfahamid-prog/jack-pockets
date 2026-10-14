import unittest

from generate import _asset_relevance, _relevant_sources


class AssetRelevanceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
