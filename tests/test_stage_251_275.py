import unittest

from nexvary_da.ui_probe import UIProbeIssue, _intersection, WidgetRecord


class Stage251275Tests(unittest.TestCase):
    def test_intersection_detects_meaningful_overlap(self):
        a = WidgetRecord("a", "Button", "A", 0, 0, 100, 40, True, "normal")
        b = WidgetRecord("b", "Button", "B", 50, 10, 100, 40, True, "normal")
        self.assertEqual(1500, _intersection(a, b))

    def test_intersection_is_zero_for_separate_widgets(self):
        a = WidgetRecord("a", "Button", "A", 0, 0, 40, 20, True, "normal")
        b = WidgetRecord("b", "Button", "B", 100, 0, 40, 20, True, "normal")
        self.assertEqual(0, _intersection(a, b))

    def test_probe_issue_is_structured(self):
        issue = UIProbeIssue("error", "clipped", ".x", "outside")
        self.assertEqual("clipped", issue.code)
        self.assertEqual("error", issue.severity)


if __name__ == "__main__":
    unittest.main()
