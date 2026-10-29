import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import assets
from assets import _archive_creator, _archive_license_is_usable, _media_license_is_usable


class ArchiveLicensePolicyTests(unittest.TestCase):
    def test_accepts_public_domain_markers(self):
        self.assertTrue(_archive_license_is_usable("https://creativecommons.org/publicdomain/zero/1.0/"))
        self.assertTrue(_archive_license_is_usable("https://creativecommons.org/publicdomain/mark/1.0/"))

    def test_accepts_attribution_license(self):
        self.assertTrue(_archive_license_is_usable("https://creativecommons.org/licenses/by/4.0/"))

    def test_rejects_sharealike_and_restricted_variants(self):
        for url in (
            "https://creativecommons.org/licenses/by-sa/4.0/",
            "https://creativecommons.org/licenses/by-nc/4.0/",
            "https://creativecommons.org/licenses/by-nd/4.0/",
            "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "https://creativecommons.org/licenses/by-nc-nd/4.0/",
        ):
            with self.subTest(url=url):
                self.assertFalse(_archive_license_is_usable(url))

    def test_media_license_requires_creator_for_cc_by(self):
        self.assertTrue(_media_license_is_usable(
            "https://creativecommons.org/licenses/by/4.0/", creator="Ada Lovelace"
        ))
        self.assertFalse(_media_license_is_usable(
            "https://creativecommons.org/licenses/by/4.0/"
        ))
        self.assertTrue(_media_license_is_usable(
            "https://creativecommons.org/publicdomain/zero/1.0/"
        ))

    def test_commons_supported_policy_requires_known_license_and_attribution(self):
        self.assertTrue(_media_license_is_usable(
            "https://creativecommons.org/licenses/by/4.0/",
            license_name="CC BY 4.0", creator="Creator",
        ))
        self.assertFalse(_media_license_is_usable(
            "https://creativecommons.org/licenses/by-sa/4.0/",
            license_name="CC BY-SA 4.0", creator="Creator",
        ))
        self.assertFalse(_media_license_is_usable(
            "", license_name="Wikimedia Commons", creator="Creator",
        ))
        self.assertTrue(_media_license_is_usable(
            "", license_name="Public domain", creator="",
        ))

    def test_commons_search_rejects_restricted_license_before_download(self):
        def metadata(license_name, license_url, artist):
            return {
                "Artist": {"value": artist},
                "LicenseShortName": {"value": license_name},
                "LicenseUrl": {"value": license_url},
                "ImageDescription": {"value": "Router equipment"},
            }

        payload = {
            "query": {"pages": {
                "1": {
                    "pageid": 1,
                    "title": "File:Restricted router.mp4",
                    "imageinfo": [{
                        "mime": "video/mp4",
                        "url": "https://upload.wikimedia.org/restricted.mp4",
                        "extmetadata": metadata(
                            "CC BY-SA 4.0",
                            "https://creativecommons.org/licenses/by-sa/4.0/",
                            "Jane Creator",
                        ),
                    }],
                },
                "2": {
                    "pageid": 2,
                    "title": "File:Allowed router.mp4",
                    "imageinfo": [{
                        "mime": "video/mp4",
                        "url": "https://upload.wikimedia.org/allowed.mp4",
                        "extmetadata": metadata(
                            "CC BY 4.0",
                            "https://creativecommons.org/licenses/by/4.0/",
                            "<span>Jane\\n    Creator</span>",
                        ),
                    }],
                },
            }}
        }

        class Response:
            ok = True
            def json(self):
                return payload

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            def fake_download(url, path):
                path.write_bytes(b"x" * 6000)
            with patch.object(assets.requests, "get", return_value=Response()), patch.object(
                assets, "_download", side_effect=fake_download
            ) as download:
                selected = assets._commons_search("router equipment", out, limit=5, kind="video")

        self.assertEqual(len(selected), 1)
        self.assertIn("commons-video-2", selected[0]["id"])
        self.assertEqual(selected[0]["license_url"], "https://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(selected[0]["credit"], "Jane Creator")
        download.assert_called_once()
        self.assertIn("allowed.mp4", download.call_args.args[0])

    def test_creator_metadata_collapses_whitespace_and_removes_markup(self):
        self.assertEqual(
            _archive_creator({"creator": "<span>Jane\n    Doe</span>"}),
            "Jane Doe",
        )

    def test_rejects_unknown_hosts_and_noncreativecommons_licenses(self):
        self.assertFalse(_archive_license_is_usable("https://example.com/licenses/by/4.0/"))
        self.assertFalse(_archive_license_is_usable("https://archive.org/about/terms.php"))
        self.assertFalse(_archive_license_is_usable(""))
        self.assertFalse(_archive_license_is_usable("not a URL"))


if __name__ == "__main__":
    unittest.main()
