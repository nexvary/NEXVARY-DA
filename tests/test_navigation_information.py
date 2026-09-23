import unittest
from urllib.parse import urlparse

from nexvary_da.ui_info import SOCIAL_LINKS, SYSTEM_SECTIONS


class NavigationInformationTests(unittest.TestCase):
    def test_about_has_all_official_channels(self):
        channels = {name: url for name, url in SOCIAL_LINKS}
        self.assertEqual("https://nexvary.com/", channels["Website"])
        self.assertIn("facebook.com/share/14p9krEn5ij", channels["Facebook"])
        self.assertEqual("mailto:info@nexvary.com", channels["Email"])
        self.assertEqual("https://www.youtube.com/@NexvaryInc", channels["YouTube"])
        self.assertEqual("https://x.com/Nexvary", channels["X"])

    def test_social_targets_are_valid(self):
        for name, url in SOCIAL_LINKS:
            parsed = urlparse(url)
            self.assertIn(parsed.scheme, {"https", "mailto"}, name)
            if parsed.scheme == "https":
                self.assertTrue(parsed.netloc, name)

    def test_system_overview_is_comprehensive(self):
        titles = {title for title, _color, _bullets in SYSTEM_SECTIONS}
        expected = {
            "Easy Mode",
            "AI & Agent Orchestration",
            "Projects & Persistent Work",
            "Build, Test & Release",
            "UI, Navigation & Quality",
            "Security",
            "Desktop & Browser Automation",
            "Media & MCP",
            "Android & GitHub",
            "Advanced Mode",
        }
        self.assertEqual(expected, titles)
        self.assertTrue(all(len(bullets) >= 2 for _title, _color, bullets in SYSTEM_SECTIONS))


if __name__ == "__main__":
    unittest.main()
