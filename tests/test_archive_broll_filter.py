import unittest

from assets import _archive_title_is_non_broll


class ArchiveBrollFilterTests(unittest.TestCase):
    def test_rejects_promotional_tv_episode_and_tutorial_titles(self):
        self.assertTrue(_archive_title_is_non_broll("GeekBeat.TV 387: WiPNET - CES 2012"))
        self.assertTrue(_archive_title_is_non_broll("Boot into OpenWrt Failsafe Mode and reflash a firmware"))
        self.assertTrue(_archive_title_is_non_broll("How to configure a router"))
        self.assertTrue(_archive_title_is_non_broll("g4tv.com-video3168: Make an Ethernet Cable"))
        self.assertTrue(_archive_title_is_non_broll("Router firmware configuration guide"))
        self.assertTrue(_archive_title_is_non_broll("Rock Band Network (360): Weebl's Stuff - Amazing Horse (Expert Keys/Vocals/Harmonies)"))

    def test_keeps_gaming_content_when_the_query_is_about_gaming(self):
        title = "Rock Band Network (360): Weebl's Stuff - Amazing Horse (Expert Keys/Vocals/Harmonies)"
        self.assertFalse(_archive_title_is_non_broll(title, "rock band gameplay music"))

    def test_keeps_general_historical_and_network_footage_titles(self):
        self.assertFalse(_archive_title_is_non_broll("1997 network outage archival news report"))
        self.assertFalse(_archive_title_is_non_broll("Router room during a major network outage"))


if __name__ == "__main__":
    unittest.main()
