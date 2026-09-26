from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexvary_da.ai_video import (
    AIVideoEngine,
    AIVideoMode,
    EngineAssessment,
    scene_to_prompt,
)
from nexvary_da.instruction_image import InstructionScene


class AIVideoRouterTests(unittest.TestCase):
    def test_scene_prompt_keeps_product_and_visual_intent(self):
        scene = InstructionScene(
            kind="cash_on_delivery",
            text="الدفع نقدًا عند الاستلام",
            narration="الدفع نقدًا عند الاستلام.",
            visual_cue="مندوب بريد يسلم المنتج للعميل والعميل يدفع له نقدًا",
        )
        prompt = scene_to_prompt(scene, product_name="Camera", model="VTS30-G-F")
        self.assertIn("Camera VTS30-G-F", prompt)
        self.assertIn("commercial", prompt.lower())
        self.assertIn("vertical 9:16", prompt)
        self.assertIn("no text baked", prompt.lower())

    def test_engine_enums_keep_supported_routing_names_stable(self):
        self.assertEqual("hybrid", AIVideoMode.HYBRID.value)
        self.assertEqual("cogvideox-2b", AIVideoEngine.COGVIDEOX.value)
        self.assertEqual("framepack", AIVideoEngine.FRAMEPACK.value)
        self.assertEqual("motion-graphics", AIVideoEngine.MOTION_GRAPHICS.value)

    def test_engine_assessment_serializes(self):
        item = EngineAssessment(
            engine="motion-graphics",
            installed=True,
            suitable=True,
            reason="fallback",
            recommended_mode="local",
        )
        payload = item.to_dict()
        self.assertTrue(payload["installed"])
        self.assertEqual("motion-graphics", payload["engine"])


if __name__ == "__main__":
    unittest.main()
