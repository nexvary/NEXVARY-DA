from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexvary_da.adaptive_memory import AdaptiveMemory


class AdaptiveMemoryTests(unittest.TestCase):
    def test_local_memory_survives_without_hindsight(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = AdaptiveMemory(Path(tmp))
            memory.retain("render", "6GB GPU recovered using direct fallback",
                          {"tier": "HYBRID", "backend": "direct"})
            recalled = memory.recall("6GB direct")
            self.assertTrue(recalled)
            self.assertEqual("local", recalled[0]["source"])
            self.assertEqual("direct", recalled[0]["payload"]["data"]["backend"])

    def test_irrelevant_local_memory_is_not_returned(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = AdaptiveMemory(Path(tmp))
            memory.retain("render", "camera advertisement", {"backend": "direct"})
            self.assertEqual([], memory.recall("unrelated-token-xyz"))


if __name__ == "__main__":
    unittest.main()
