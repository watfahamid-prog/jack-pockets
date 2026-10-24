import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from music import _download_limited


class MusicDownloadLimitTests(unittest.TestCase):
    def test_rejects_oversized_content_length_before_writing(self):
        response = Mock(headers={"content-length": "101"})
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "track.source"
            with self.assertRaisesRegex(RuntimeError, "exceeds 100-byte limit"):
                _download_limited(response, destination, limit=100)
            self.assertFalse(destination.exists())
            response.iter_content.assert_not_called()

    def test_stops_stream_when_actual_bytes_exceed_limit(self):
        response = Mock(headers={})
        response.iter_content.return_value = [b"a" * 60, b"b" * 50]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "track.source"
            with self.assertRaisesRegex(RuntimeError, "exceeds 100-byte limit"):
                _download_limited(response, destination, limit=100)
            self.assertEqual(destination.stat().st_size, 60)

    def test_accepts_download_at_limit(self):
        response = Mock(headers={"content-length": "5"})
        response.iter_content.return_value = [b"hello"]
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "track.source"
            self.assertEqual(_download_limited(response, destination, limit=5), 5)
            self.assertEqual(destination.read_bytes(), b"hello")


if __name__ == "__main__":
    unittest.main()
