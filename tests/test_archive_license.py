import unittest

from assets import _archive_license_is_usable


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

    def test_rejects_unknown_hosts_and_noncreativecommons_licenses(self):
        self.assertFalse(_archive_license_is_usable("https://example.com/licenses/by/4.0/"))
        self.assertFalse(_archive_license_is_usable("https://archive.org/about/terms.php"))
        self.assertFalse(_archive_license_is_usable(""))
        self.assertFalse(_archive_license_is_usable("not a URL"))


if __name__ == "__main__":
    unittest.main()
