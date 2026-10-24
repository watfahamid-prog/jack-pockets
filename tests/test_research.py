import unittest
from unittest.mock import patch
import research

class ResearchTests(unittest.TestCase):
    def test_uses_cached_results_without_network(self):
        cached = [{"title": "Source", "url": "https://example.com/source", "content": "Evidence"}]
        with patch.object(research, "load_json_cache", return_value=cached), patch.object(research, "_perplexity") as search:
            self.assertEqual(research.search_web("topic", limit=3), cached)
            search.assert_not_called()

    def test_fallback_deduplicates_urls_and_caches_results(self):
        results = [{"title": "A", "url": "https://example.com/a"}, {"title": "duplicate", "url": "https://example.com/a"}]
        with patch.object(research, "load_json_cache", return_value=None), patch.object(research, "_perplexity", side_effect=RuntimeError("offline")), patch.object(research, "_tavily", return_value=results), patch.object(research, "_wikipedia", return_value=[]), patch.object(research, "_europe_pmc", return_value=[]), patch.object(research, "save_json_cache") as save:
            result = research.search_web("ordinary topic", limit=4)
        self.assertEqual(len(result), 1)
        save.assert_called_once()

    def test_http_url_validation(self):
        self.assertFalse(research._valid_http_url("file:///tmp/example"))
        self.assertTrue(research._valid_http_url("https://example.com"))

if __name__ == "__main__":
    unittest.main()
