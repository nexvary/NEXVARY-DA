import tempfile
import unittest
from pathlib import Path

from PIL import Image

from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.product_ad import ProductAdBrief, ProductAdComposer, build_arabic_product_script
from nexvary_da.state import ProjectState


def guard_for(root: Path, *permissions: Permission) -> WorkspaceGuard:
    return WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, *permissions}, "test")])


class ProductAdTests(unittest.TestCase):
    def test_script_uses_only_supplied_product_facts(self):
        brief = ProductAdBrief(
            product_name="منشار كهربائي",
            model="X24",
            price="5500",
            currency="EGP",
            details="مقاس 24 بوصة\nالاستلام من العاشر من رمضان",
            contact="01000000000",
            target_seconds=60,
        )
        result = build_arabic_product_script(brief)
        self.assertIn("منشار كهربائي", result.text)
        self.assertIn("X24", result.text)
        self.assertIn("5500", result.text)
        self.assertIn("24 بوصة", result.text)
        self.assertIn("العاشر من رمضان", result.text)
        self.assertIn("01000000000", result.text)
        self.assertNotIn("ضمان", result.text)
        self.assertNotIn("الأفضل", result.text)

    def test_short_brief_is_flagged_instead_of_inventing_padding(self):
        result = build_arabic_product_script(
            ProductAdBrief("", "A1", "1000", target_seconds=60)
        )
        self.assertTrue(result.needs_more_details)
        self.assertLess(result.estimated_seconds, 60)

    def test_image_import_and_portrait_frame_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (640, 480), "white").save(source)
            state = ProjectState(root)
            try:
                composer = ProductAdComposer(
                    guard_for(root, Permission.WRITE),
                    state,
                    root,
                )
                imported = composer.import_selected_images([str(source)])
                frames = composer.render_frames(
                    imported,
                    ProductAdBrief("منتج تجريبي", "M-1", "250", "EGP"),
                )
                self.assertEqual(1, len(frames))
                self.assertTrue(frames[0].is_file())
                with Image.open(frames[0]) as rendered:
                    self.assertEqual((1080, 1920), rendered.size)
            finally:
                state.close()


if __name__ == "__main__":
    unittest.main()
