import unittest

from assets import _archive_title_is_non_broll


class ArchiveBrollFilterTests(unittest.TestCase):
    def test_rejects_promotional_tv_episode_and_tutorial_titles(self):
        self.assertTrue(_archive_title_is_non_broll("GeekBeat.TV 387: WiPNET - CES 2012"))
        self.assertTrue(_archive_title_is_non_broll("Boot into OpenWrt Failsafe Mode and reflash a firmware"))
        self.assertTrue(_archive_title_is_non_broll("How to configure a router"))

    def test_keeps_general_historical_and_network_footage_titles(self):
        self.assertFalse(_archive_title_is_non_broll("1997 network outage archival news report"))
        self.assertFalse(_archive_title_is_non_broll("Router room during a major network outage"))


if __name__ == "__main__":
    unittest.main()
