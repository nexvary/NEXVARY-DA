from __future__ import annotations

import unittest

from nexvary_da.ai_scene import collect_comfy_output_records, patch_comfy_workflow


class AISceneWorkflowTests(unittest.TestCase):
    def test_patches_exported_comfy_workflow_without_node_ids(self):
        workflow = {
            "1": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "old positive", "clip": ["9", 1]},
                "_meta": {"title": "Positive Prompt"},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "old negative", "clip": ["9", 1]},
                "_meta": {"title": "Negative Prompt"},
            },
            "3": {
                "class_type": "LoadImage",
                "inputs": {"image": "old.png"},
            },
            "4": {
                "class_type": "SaveImage",
                "inputs": {"images": ["8", 0], "filename_prefix": "old"},
            },
        }
        patched = patch_comfy_workflow(
            workflow,
            prompt="commercial delivery scene",
            negative_prompt="watermark",
            input_image="input/product.png",
            output_prefix="nexvary-test",
        )
        self.assertEqual("commercial delivery scene", patched["1"]["inputs"]["text"])
        self.assertEqual("watermark", patched["2"]["inputs"]["text"])
        self.assertEqual("input/product.png", patched["3"]["inputs"]["image"])
        self.assertEqual("nexvary-test", patched["4"]["inputs"]["filename_prefix"])
        self.assertEqual("old positive", workflow["1"]["inputs"]["text"])

    def test_placeholder_workflow_is_supported(self):
        workflow = {
            "1": {
                "class_type": "CustomPromptNode",
                "inputs": {
                    "prompt": "${PROMPT}",
                    "negative": "${NEGATIVE_PROMPT}",
                    "image": "${INPUT_IMAGE}",
                    "prefix": "${OUTPUT_PREFIX}",
                },
            }
        }
        patched = patch_comfy_workflow(
            workflow,
            prompt="scene prompt",
            negative_prompt="bad anatomy",
            input_image="product.png",
            output_prefix="ad-01",
        )
        values = patched["1"]["inputs"]
        self.assertEqual("scene prompt", values["prompt"])
        self.assertEqual("bad anatomy", values["negative"])
        self.assertEqual("product.png", values["image"])
        self.assertEqual("ad-01", values["prefix"])

    def test_collects_image_and_video_style_comfy_outputs(self):
        history = {
            "outputs": {
                "10": {
                    "images": [
                        {"filename": "a.png", "subfolder": "x", "type": "output"},
                    ]
                },
                "11": {
                    "gifs": [
                        {"filename": "b.mp4", "subfolder": "", "type": "output"},
                    ]
                },
            }
        }
        records = collect_comfy_output_records(history)
        self.assertEqual(2, len(records))
        self.assertEqual("a.png", records[0]["filename"])
        self.assertEqual("b.mp4", records[1]["filename"])


if __name__ == "__main__":
    unittest.main()
