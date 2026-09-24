from __future__ import annotations

import unittest

from nexvary_da.instruction_image import (
    InstructionSceneKind,
    plan_instruction_scenes,
)
from nexvary_da.product_ad import ProductAdBrief, build_arabic_product_script


class InstructionImageTests(unittest.TestCase):
    def test_shipping_instruction_maps_to_shipping_visual(self):
        scenes = plan_instruction_scenes("الشحن عن طريق البريد إلى جميع المحافظات")
        self.assertEqual(1, len(scenes))
        self.assertEqual(InstructionSceneKind.SHIPPING.value, scenes[0].kind)
        self.assertIn("سيارة بريد", scenes[0].visual_cue)

    def test_cash_collection_maps_to_handoff_scene(self):
        scenes = plan_instruction_scenes("مندوب البريد يستلم المال نقدا عند تسليم المنتج")
        self.assertEqual(InstructionSceneKind.CASH_ON_DELIVERY.value, scenes[0].kind)
        self.assertIn("مندوب بريد", scenes[0].visual_cue)
        self.assertIn("نقد", scenes[0].visual_cue)

    def test_purchase_and_setup_images_can_create_multiple_scene_types(self):
        text = (
            "الاستلام من المخزن أفضل خيار\n"
            "احجز الآن لتضمن توفر الكمية\n"
            "الضمان داخل الدولة\n"
            "حمّل التطبيق من Google Play\n"
            "امسح رمز QR"
        )
        kinds = {scene.kind for scene in plan_instruction_scenes(text)}
        self.assertIn(InstructionSceneKind.PICKUP.value, kinds)
        self.assertIn(InstructionSceneKind.RESERVATION.value, kinds)
        self.assertIn(InstructionSceneKind.WARRANTY.value, kinds)
        self.assertIn(InstructionSceneKind.APP.value, kinds)
        self.assertIn(InstructionSceneKind.QR.value, kinds)

    def test_seller_image_text_is_narrated_as_seller_instruction(self):
        brief = ProductAdBrief(
            product_name="Camera",
            model="VTS30-G-F",
            price="2500",
            target_seconds=60,
        )
        script = build_arabic_product_script(
            brief,
            seller_instructions=(
                "الشحن عن طريق البريد.",
                "الدفع نقدًا عند الاستلام.",
            ),
        )
        self.assertIn("التعليمات الموجودة في الصور", script.text)
        self.assertIn("الشحن عن طريق البريد", script.text)
        self.assertIn("الدفع نقدًا عند الاستلام", script.text)


if __name__ == "__main__":
    unittest.main()
