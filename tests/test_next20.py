import tempfile
import time
import unittest
from pathlib import Path

from nexvary_da.change_tracker import ProjectChangeTracker
from nexvary_da.ui_theme import PALETTE, scale_for_screen, status_color
from nexvary_da.validation_cache import ValidationCache


class NextTwentyPassTests(unittest.TestCase):
    def test_theme_has_distinct_dark_gold_and_status_tokens(self):
        self.assertNotEqual(PALETTE.background, PALETTE.surface)
        self.assertNotEqual(PALETTE.gold, PALETTE.blue)
        self.assertEqual(PALETTE.success, status_color("PASS"))
        self.assertEqual(PALETTE.danger, status_color("FAIL"))
        self.assertGreater(scale_for_screen(2560, 1440), 1.0)

    def test_change_tracker_detects_add_modify_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracker = ProjectChangeTracker(root)
            target = root / "demo.txt"
            target.write_text("one", encoding="utf-8")
            added = tracker.poll()
            self.assertEqual(("demo.txt",), added.added)
            time.sleep(0.002)
            target.write_text("two-two", encoding="utf-8")
            modified = tracker.poll()
            self.assertEqual(("demo.txt",), modified.modified)
            target.unlink()
            deleted = tracker.poll()
            self.assertEqual(("demo.txt",), deleted.deleted)

    def test_tracker_ignores_build_and_control_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".nexvary-da").mkdir()
            (root / "build").mkdir()
            (root / ".nexvary-da" / "state.sqlite3").write_text("x")
            (root / "build" / "artifact.bin").write_text("x")
            tracker = ProjectChangeTracker(root)
            self.assertEqual({}, tracker.snapshot())

    def test_validation_cache_key_changes_with_file_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".nexvary-da").mkdir()
            target = root / "a.py"
            target.write_text("A = 1\n", encoding="utf-8")
            cache = ValidationCache(root)
            first = cache.make_key(mode="engineer", changed_files=["a.py"], commit="abc")
            target.write_text("A = 2\n", encoding="utf-8")
            second = cache.make_key(mode="engineer", changed_files=["a.py"], commit="abc")
            self.assertNotEqual(first, second)

    def test_validation_cache_round_trip_is_bounded_and_clearable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = ValidationCache(root)
            for index in range(5):
                cache.put(str(index), {"complete": True, "n": index}, max_entries=3)
            self.assertIsNone(cache.get("0"))
            self.assertEqual(4, cache.get("4")["n"])
            cache.clear()
            self.assertIsNone(cache.get("4"))


if __name__ == "__main__":
    unittest.main()
