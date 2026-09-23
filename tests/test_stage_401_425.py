import unittest

from nexvary_da.ui_theme import PALETTE, section_color, status_color


class Stage401425VisualTests(unittest.TestCase):
    def test_action_green_is_reserved_from_success_state(self):
        self.assertNotEqual(PALETTE.action.lower(), PALETTE.success.lower())
        self.assertEqual(PALETTE.success, status_color("PASS"))
        self.assertNotEqual(PALETTE.action, status_color("READY"))

    def test_neon_sections_are_visually_distinct(self):
        colors = {
            section_color("task"),
            section_color("build"),
            section_color("tools"),
            section_color("media"),
            section_color("video"),
            section_color("voice"),
        }
        self.assertGreaterEqual(len(colors), 6)

    def test_silver_frame_has_bright_and_dark_edges(self):
        self.assertNotEqual(PALETTE.silver, PALETTE.silver_bright)
        self.assertNotEqual(PALETTE.border, PALETTE.silver_bright)


if __name__ == "__main__":
    unittest.main()
