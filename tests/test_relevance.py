import unittest

from relevance import _collect_source_urls, _evidence_url_errors, _sources_for_urls, _asset_relevance, _asset_search_queries, _relevant_sources
from unittest.mock import patch

import semantic_ranker


class ApprovedResearchTests(unittest.TestCase):
    def test_only_sources_for_urls_are_returned_in_approval_order(self):
        weak = {"url": "https://example.org/weak", "title": "Weak unrelated result"}
        strong = {"url": "https://example.org/strong", "title": "Strong matching source"}
        result = _sources_for_urls(
            [weak, strong],
            ["https://example.org/strong", "https://example.org/not-returned"],
        )
        self.assertEqual(result, [strong])
        self.assertNotIn(weak, result)

    def test_sources_for_urls_are_deduplicated_and_ignore_bad_records(self):
        source = {"url": "https://example.org/source", "title": "Source"}
        result = _sources_for_urls(
            [None, {}, source, {"url": "https://example.org/source", "title": "duplicate"}],
            ["https://example.org/source", "https://example.org/source"],
        )
        self.assertEqual(result, [source])

    def test_empty_selected_list_produces_no_displayable_sources(self):
        result = _sources_for_urls([{"url": "https://example.org/source"}], [])
        self.assertEqual(result, [])

    def test_evidence_gate_rejects_beats_without_sources(self):
        errors = _evidence_url_errors([
            {"id": "b1", "source_urls": []},
            {"id": "b2", "source_urls": ["https://example.org/valid"]},
        ])
        self.assertEqual(
            errors,
            ["evidence gate: beat has no supporting source_urls: b1"],
        )

    def test_evidence_gate_rejects_non_http_citation_urls(self):
        errors = _evidence_url_errors([
            {"id": "b1", "source_urls": ["javascript:alert(1)"]},
        ])
        self.assertEqual(
            errors,
            ["evidence gate: invalid source URL in b1"],
        )

    def test_manifest_source_urls_include_only_selected_beat_sources(self):
        result = _collect_source_urls([
            {"source_urls": ["https://example.org/a", "https://example.org/b"]},
            {"source_urls": ["https://example.org/b", "", None]},
            {"source_urls": []},
        ])
        self.assertEqual(result, ["https://example.org/a", "https://example.org/b"])


class AssetRelevanceTests(unittest.TestCase):
    def test_media_queries_use_short_subject_phrases_not_full_visual_directions(self):
        beat = {
            "title": "The Emerging Frontier: Commercial Space and Lunar Property",
            "keywords": ["lunar outpost", "artemis accords", "moon property", "commercial space"],
            "visual_intent": "Cinematic sequence sweeping over a generated line-art graphic of lunar surface mapping",
            "narration": "As commercial spaceflight accelerates, the definition of wealth is expanding.",
        }
        queries = _asset_search_queries(beat, limit=3)
        self.assertEqual(queries[0], "lunar outpost artemis accords")
        self.assertEqual(queries[1], "lunar outpost commercial space")
        self.assertEqual(queries[2], "moon property commercial space")
        self.assertTrue(all(len(query.split()) <= 5 for query in queries))

    def test_long_keyword_phrases_stay_separate_and_bounded(self):
        beat = {
            "title": "The One Hundred and Fifty Billion Dollar Machine",
            "keywords": [
                "international space station full view solar arrays",
                "nasa mission control room houston operations",
            ],
            "visual_intent": "Full-station exterior tracking shot of the ISS with solar arrays, then NASA flight controllers in Houston.",
        }
        queries = _asset_search_queries(beat, limit=2)
        self.assertEqual(queries, [
            "international space station full view",
            "nasa mission control room houston",
        ])
        self.assertTrue(all(len(query.split()) <= 5 for query in queries))
        self.assertNotIn("dollar", " ".join(queries).lower())

    def test_media_queries_prioritize_specific_keywords_over_generic_chapter_title(self):
        beat = {
            "title": "The Emerging Frontier: Celestial Real Estate",
            "keywords": ["lunar outpost", "Artemis Accords", "moon surface"],
            "visual_intent": "NASA lunar lander on the Moon",
            "narration": "The next lunar outpost depends on NASA missions and surface access.",
        }
        queries = _asset_search_queries(beat, limit=4)
        self.assertEqual(queries[0], "lunar outpost Artemis Accords")
        self.assertEqual(queries[1], "lunar outpost moon surface")
        self.assertNotEqual(queries[0], beat["title"])
        self.assertLessEqual(len(queries), 4)

    def test_media_queries_normalize_repeated_whitespace(self):
        beat = {
            "title": "Lunar surface operations",
            "keywords": ["lunar   outpost", "artemis    accords"],
            "visual_intent": "",
        }
        queries = _asset_search_queries(beat, limit=1)
        self.assertEqual(queries, ["lunar outpost artemis accords"])

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

    def test_asset_relevance_accepts_keyword_string_as_well_as_list(self):
        asset = {
            "title": "Router network routing equipment",
            "description": "",
            "tags": [],
        }
        list_beat = {"title": "An obscure routing incident", "keywords": ["router", "network"]}
        string_beat = {"title": "An obscure routing incident", "keywords": "router network"}
        self.assertEqual(
            _asset_relevance("router network", list_beat, asset),
            _asset_relevance("router network", string_beat, asset),
        )
        self.assertTrue(_asset_relevance("router network", string_beat, asset)[0])

    def test_asset_relevance_treats_null_keywords_as_empty_without_crashing(self):
        asset = {"title": "Router network routing equipment", "description": "", "tags": []}
        for beat in ({"title": "Unrelated event", "keywords": None}, {"title": "Unrelated event"}):
            relevant, matched = _asset_relevance("router network", beat, asset)
            self.assertFalse(relevant)
            self.assertEqual(matched, ["network", "router"])

    def test_singular_and_plural_subject_terms_match_without_substring_matching(self):
        beat = {
            "title": "Internet router network",
            "keywords": ["router network"],
        }
        plural_metadata = {
            "title": "Routers and network switches",
            "description": "Networks connected through routing equipment",
            "tags": ["routers", "networks"],
        }
        relevant, matched = _asset_relevance("router network", beat, plural_metadata)
        self.assertTrue(relevant)
        self.assertEqual(matched, ["network", "router"])

        singular_metadata = {
            "title": "Router network routing equipment",
            "description": "",
            "tags": [],
        }
        relevant_reverse, matched_reverse = _asset_relevance(
            "routers networks", beat, singular_metadata
        )
        self.assertTrue(relevant_reverse)
        self.assertEqual(matched_reverse, ["network", "router"])

    def test_plural_normalization_does_not_turn_news_into_new(self):
        beat = {"title": "Daily news report", "keywords": ["news"]}
        asset = {"title": "New car on a road", "description": "", "tags": []}
        relevant, matched = _asset_relevance("news", beat, asset)
        self.assertFalse(relevant)
        self.assertEqual(matched, [])

    def test_accepts_core_technical_subject_when_title_omits_query_modifiers(self):
        beat = {
            "title": "The April 1997 Black Hole",
            "keywords": ["1990s server room rack", "dial internet vintage computer", "network outage monitor graph"],
        }
        asset = {"title": "Database storage of a server", "description": "", "tags": []}
        relevant, matched = _asset_relevance("1990s server room rack", beat, asset)
        self.assertTrue(relevant)
        self.assertEqual(matched, ["server"])

    def test_rejects_modifier_only_match_from_unrelated_vintage_telephone(self):
        beat = {
            "title": "The April 1997 Black Hole",
            "keywords": ["1990s server room rack", "dial internet vintage computer", "network outage monitor graph"],
        }
        asset = {"title": "A man talking to someone using a vintage telephone", "description": "", "tags": []}
        relevant, matched = _asset_relevance("dial internet vintage computer", beat, asset)
        self.assertFalse(relevant)
        self.assertEqual(matched, [])

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

    def test_rejects_asset_that_matches_other_beat_keywords_but_not_search_query(self):
        beat = {
            "title": "The Persistent Phantom",
            "keywords": [
                "ethernet cable disconnected server back",
                "terminal screen clearing memory cache",
                "network engineer typing frantically 1990s",
            ],
        }
        asset = {
            "title": "Terminal screen clearing memory cache",
            "description": "A network engineer typing frantically.",
            "tags": [],
        }
        relevant, matched = _asset_relevance(
            "ethernet cable disconnected server back", beat, asset
        )
        self.assertFalse(relevant)
        self.assertLess(len(matched), 3)

    def test_accepts_multiple_active_query_hits_for_a_long_query(self):
        beat = {
            "title": "The Persistent Phantom",
            "keywords": ["ethernet cable disconnected server back"],
        }
        asset = {
            "title": "Ethernet network product demo",
            "description": "A demo of Ethernet over coax cable.",
            "tags": [],
        }
        relevant, matched = _asset_relevance(
            "ethernet cable disconnected server back", beat, asset
        )
        self.assertTrue(relevant)
        self.assertEqual(matched, ["cable", "ethernet"])

    def test_accepts_two_term_short_subject_query(self):
        beat = {"title": "The Glue of the Web", "keywords": ["router network"]}
        asset = {"title": "Router network routing equipment", "description": "", "tags": []}
        relevant, matched = _asset_relevance("router network", beat, asset)
        self.assertTrue(relevant)
        self.assertEqual(matched, ["network", "router"])

    def test_accepts_specific_subject_match_when_stock_title_omits_modifiers(self):
        beat = {
            "title": "The Black Hole Effect",
            "keywords": ["oscilloscope data signal drop flatline"],
        }
        asset = {
            "title": "Close up of oscilloscope with waveform display",
            "description": "An oscilloscope in operation.",
            "tags": [],
        }
        relevant, matched = _asset_relevance(
            "oscilloscope data signal drop flatline", beat, asset
        )
        self.assertTrue(relevant)
        self.assertIn("oscilloscope", matched)

    def test_rejects_asset_that_matches_other_beat_keywords_but_not_active_query(self):
        beat = {
            "title": "The Persistent Phantom",
            "keywords": [
                "ethernet cable disconnected server back",
                "terminal screen clearing memory cache",
                "network engineer typing frantically 1990s",
            ],
        }
        asset = {
            "title": "A river bank in autumn",
            "description": "Beautiful autumn scenery.",
            "tags": [],
        }
        relevant, matched = _asset_relevance(
            "ethernet cable disconnected server back", beat, asset
        )
        self.assertFalse(relevant)
        self.assertEqual(matched, [])

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

    def test_rejects_topic_overlap_when_source_misses_beat_keywords(self):
        sources = [{
            "url": "https://example.org/expensive-diamonds",
            "title": "The world's most expensive diamonds",
            "content": "Expensive diamonds attract wealthy buyers and record prices.",
        }]
        result = _relevant_sources(
            "The world's most expensive diamonds",
            {
                "title": "The Pink Star Auction",
                "keywords": ["Pink Star diamond", "auction price"],
                "narration": "The diamond sold for a record price at a major auction.",
            },
            sources,
        )
        self.assertEqual(result, [])

    def test_keeps_source_with_curated_beat_keyword_overlap(self):
        sources = [{
            "url": "https://example.org/pink-star-auction",
            "title": "Pink Star diamond auction record",
            "content": "The Pink Star diamond sold at auction for a record price.",
        }]
        result = _relevant_sources(
            "The world's most expensive diamonds",
            {
                "title": "The Pink Star Auction",
                "keywords": ["Pink Star diamond", "auction price"],
                "narration": "The diamond sold for a record price at a major auction.",
            },
            sources,
        )
        self.assertEqual(result, ["https://example.org/pink-star-auction"])

    def test_prioritizes_authoritative_sources_over_wikipedia_and_blogs(self):
        sources = [
            {
                "url": "https://blog.crawlex.net/blog/bgp-hijacks-route-leaks/",
                "title": "BGP hijacks and route leaks",
                "content": "AS 7007 router network routing incident April 1997.",
            },
            {
                "url": "https://en.wikipedia.org/wiki/AS_7007_incident",
                "title": "AS 7007 incident",
                "content": "Router network routing incident April 1997.",
            },
            {
                "url": "https://nanog.org/stories/articles/a-brief-history-of-the-internets-biggest-bgp-incidents/",
                "title": "A Brief History of the Internet's Biggest BGP Incidents",
                "content": "AS 7007 router network routing incident in April 1997.",
            },
            {
                "url": "https://www.wired.com/1997/04/net-outage-the-oops-heard-round-the-world/",
                "title": "Net Outage: The Oops Heard Round the World",
                "content": "April 1997 AS 7007 router network routing incident.",
            },
        ]
        result = _relevant_sources(
            "AS 7007 routing incident",
            {"title": "The April 1997 Black Hole", "narration": "The router leaked network routes."},
            sources,
            limit=3,
        )
        self.assertEqual(result, [
            "https://nanog.org/stories/articles/a-brief-history-of-the-internets-biggest-bgp-incidents/",
            "https://www.wired.com/1997/04/net-outage-the-oops-heard-round-the-world/",
        ])

    def test_specific_contemporary_source_outranks_general_paper(self):
        sources = [
            {
                "url": "https://crypto.stanford.edu/cs155old/cs155-spring10/papers/BGP-security.pdf",
                "title": "A Survey of BGP Security",
                "content": "BGP security and routing protocol mechanisms.",
            },
            {
                "url": "https://www.wired.com/1997/04/net-outage-the-oops-heard-round-the-world/",
                "title": "Net Outage: The Oops Heard Round the World",
                "content": "On April 25, 1997, AS 7007 caused a router routing incident and Internet outage.",
            },
        ]
        result = _relevant_sources(
            "AS 7007 routing incident",
            {"title": "The April 1997 Black Hole", "narration": "A router leaked routes and disrupted the network."},
            sources,
            limit=2,
        )
        self.assertEqual(result[0], "https://www.wired.com/1997/04/net-outage-the-oops-heard-round-the-world/")
        self.assertIn("https://crypto.stanford.edu/cs155old/cs155-spring10/papers/BGP-security.pdf", result)

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
