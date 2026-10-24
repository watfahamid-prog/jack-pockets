import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import assets
from assets import _download, search_archive_videos, search_commons_videos, search_pixabay_videos, search_pexels_videos


class BoundedAssetDownloadTests(unittest.TestCase):
    def test_download_rejects_declared_oversize_file_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversize.mp4"
            response = MagicMock()
            response.__enter__.return_value = response
            response.headers = {"content-length": "200"}
            response.raise_for_status.return_value = None

            with patch("assets.requests.get", return_value=response):
                with self.assertRaisesRegex(ValueError, "exceeds size limit"):
                    _download("https://example.test/oversize.mp4", path, max_bytes=100)

            self.assertFalse(path.exists())

    def test_download_removes_partial_file_when_stream_exceeds_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversize.mp4"
            response = MagicMock()
            response.__enter__.return_value = response
            response.headers = {}
            response.raise_for_status.return_value = None
            response.iter_content.return_value = [b"a" * 60, b"b" * 60]

            with patch("assets.requests.get", return_value=response):
                with self.assertRaisesRegex(ValueError, "exceeded size limit"):
                    _download("https://example.test/oversize.mp4", path, max_bytes=100)

            self.assertFalse(path.exists())

    def test_download_enforces_episode_wide_budget_across_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(assets, "MAX_TOTAL_ASSET_DOWNLOAD_BYTES", 100):
            assets.reset_asset_download_budget()
            first = Path(directory) / "first.mp4"
            second = Path(directory) / "second.mp4"
            response_one = MagicMock()
            response_one.__enter__.return_value = response_one
            response_one.headers = {}
            response_one.raise_for_status.return_value = None
            response_one.iter_content.return_value = [b"a" * 60]
            response_two = MagicMock()
            response_two.__enter__.return_value = response_two
            response_two.headers = {}
            response_two.raise_for_status.return_value = None
            response_two.iter_content.return_value = [b"b" * 50]

            with patch("assets.requests.get", side_effect=[response_one, response_two]):
                _download("https://example.test/first.mp4", first, max_bytes=100)
                with self.assertRaisesRegex(ValueError, "exceeded size limit"):
                    _download("https://example.test/second.mp4", second, max_bytes=100)

            self.assertEqual(first.stat().st_size, 60)
            self.assertFalse(second.exists())
            self.assertEqual(assets._ASSET_BYTES_DOWNLOADED, 60)
            assets.reset_asset_download_budget()

    def test_pexels_unrelated_video_is_rejected_before_download(self):
        def fake_download(_url, path, *_args, **_kwargs):
            Path(path).write_bytes(b"x" * 6000)

        data = {
            "videos": [
                {
                    "id": 1,
                    "url": "https://www.pexels.com/video/mountain-hiking-123",
                    "video_files": [{"file_type": "video/mp4", "link": "https://example.test/mountain.mp4", "width": 1280, "height": 720, "fps": 30}],
                },
                {
                    "id": 2,
                    "url": "https://www.pexels.com/video/rare-emerald-necklace-auction-456",
                    "video_files": [{"file_type": "video/mp4", "link": "https://example.test/emerald.mp4", "width": 1280, "height": 720, "fps": 30}],
                },
            ]
        }
        beat = {"title": "Rare emerald necklace auction", "keywords": ["emerald", "necklace", "auction"]}

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"PEXELS_API_KEY": "test-key"}), patch.object(assets, "_PEXELS_DISABLED", False), patch("assets._get", return_value=data), patch("assets._download", side_effect=fake_download) as download:
            result = search_pexels_videos("emerald necklace auction", Path(directory), limit=2, beat=beat)

        self.assertEqual([item["id"] for item in result], ["pexels-video-2"])
        self.assertEqual(download.call_count, 1)

    def test_pixabay_unrelated_video_is_rejected_before_download(self):
        def fake_download(_url, path, *_args, **_kwargs):
            Path(path).write_bytes(b"x" * 6000)

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "hits": [
                {"id": 1, "tags": "mountain, hiking, landscape", "videos": {"large": {"url": "https://example.test/mountain.mp4", "width": 1920, "height": 1080}}},
                {"id": 2, "tags": "emerald, necklace, auction", "videos": {"large": {"url": "https://example.test/emerald.mp4", "width": 1920, "height": 1080}}, "pageURL": "https://pixabay.com/videos/emerald-auction-2/"},
            ]
        }
        beat = {"title": "Rare emerald necklace auction", "keywords": ["emerald", "necklace", "auction"]}

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"PIXABAY_API_KEY": "test-key"}), patch("assets.requests.get", return_value=response), patch("assets._download", side_effect=fake_download) as download:
            result = search_pixabay_videos("emerald necklace auction", Path(directory), limit=2, beat=beat)

        self.assertEqual([item["id"] for item in result], ["pixabay-video-2"])
        self.assertEqual(download.call_count, 1)

    def test_commons_unrelated_clip_is_rejected_before_download(self):
        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "title": "File:River bank documentary footage.mp4",
                        "imageinfo": [{
                            "mime": "video/mp4",
                            "url": "https://example.test/river.mp4",
                            "thumburl": "",
                            "extmetadata": {
                                "ImageDescription": {"value": "A river bank with hikers"},
                                "LicenseShortName": {"value": "CC BY-SA"},
                            },
                        }],
                    }
                }
            }
        }
        beat = {"title": "Rare emerald necklace auction", "keywords": ["emerald", "necklace", "auction"]}

        with tempfile.TemporaryDirectory() as directory, patch("assets.requests.get", return_value=response), patch("assets._download") as download:
            result = search_commons_videos("emerald necklace auction", Path(directory), limit=2, beat=beat)

        self.assertEqual(result, [])
        download.assert_not_called()

    def test_archive_unrelated_clip_is_rejected_before_metadata_fetch(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "response": {
                "docs": [{
                    "identifier": "river-footage",
                    "title": "River bank footage",
                    "description": "Hikers crossing a river",
                    "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
                }]
            }
        }
        beat = {"title": "Rare emerald necklace auction", "keywords": ["emerald", "necklace", "auction"]}

        with tempfile.TemporaryDirectory() as directory, patch("assets.requests.get", return_value=response) as request:
            result = search_archive_videos("emerald necklace", Path(directory), limit=2, beat=beat)

        self.assertEqual(result, [])
        self.assertTrue(all("advancedsearch.php" in call.args[0] for call in request.call_args_list))
        self.assertFalse(any("/metadata/" in call.args[0] for call in request.call_args_list))


if __name__ == "__main__":
    unittest.main()
