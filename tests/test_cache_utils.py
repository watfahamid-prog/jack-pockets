from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cache_utils


class JsonCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {
            "JACKPOCKETS_CACHE_DIR": self.temp_dir.name,
            "JACKPOCKETS_CACHE_TTL_SECONDS": "3600",
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_round_trip_returns_cached_value(self):
        payload = {"topic": "Apollo 11", "limit": 8}
        value = [{"title": "NASA", "url": "https://nasa.gov"}]
        cache_utils.save_json_cache("research", payload, value)
        self.assertEqual(cache_utils.load_json_cache("research", payload), value)

    def test_corrupt_cache_is_ignored(self):
        payload = {"topic": "corrupt"}
        path = (
            Path(self.temp_dir.name) / "json" / "research" /
            (cache_utils.cache_key("research", payload) + ".json")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        self.assertIsNone(cache_utils.load_json_cache("research", payload))

    def test_disabled_cache_does_not_read_or_write(self):
        payload = {"topic": "disabled"}
        with patch.dict(os.environ, {"JACKPOCKETS_DISABLE_CACHE": "1"}):
            cache_utils.save_json_cache("research", payload, {"ok": True})
            self.assertIsNone(cache_utils.load_json_cache("research", payload))
        path = (
            Path(self.temp_dir.name) / "json" / "research" /
            (cache_utils.cache_key("research", payload) + ".json")
        )
        self.assertFalse(path.exists())

    def test_expired_entry_is_ignored(self):
        payload = {"topic": "expired"}
        cache_utils.save_json_cache("research", payload, {"ok": True})
        path = (
            Path(self.temp_dir.name) / "json" / "research" /
            (cache_utils.cache_key("research", payload) + ".json")
        )
        record = json.loads(path.read_text(encoding="utf-8"))
        record["created_at"] = 1
        path.write_text(json.dumps(record), encoding="utf-8")
        self.assertIsNone(cache_utils.load_json_cache("research", payload))


if __name__ == "__main__":
    unittest.main()
