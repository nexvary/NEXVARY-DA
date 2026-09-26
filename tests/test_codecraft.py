from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.codecraft import CodeCraftProvider, _json_from_text, _scene_kind
from nexvary_da.instruction_image import InstructionSceneKind
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.secret_store import SecretStore
from nexvary_da.state import ProjectState


class _Settings:
    def get(self, key, env_name="", default=None):
        values = {
            "codecraft_base_url": "https://www.codecraftapi.com/v1",
        }
        return values.get(key, default or "")


class _Provider(CodeCraftProvider):
    def _request_json(self, method, endpoint, *, body=None, timeout=45.0):
        if endpoint == "/models":
            return {
                "object": "list",
                "data": [
                    {
                        "id": "text-cheap",
                        "name": "Text",
                        "context_window": 100000,
                        "capabilities": ["streaming"],
                        "pricing": {"input_per_1k": 0.00001, "output_per_1k": 0.00002},
                    },
                    {
                        "id": "vision-json",
                        "name": "Vision JSON",
                        "context_window": 128000,
                        "capabilities": ["vision", "json_mode", "reasoning"],
                        "pricing": {"input_per_1k": 0.0001, "output_per_1k": 0.0002},
                    },
                ],
            }, {}
        raise AssertionError(endpoint)


class CodeCraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        guard = WorkspaceGuard(
            [
                WorkspacePolicy.create(
                    self.root,
                    {Permission.READ, Permission.WRITE, Permission.NETWORK},
                    "test",
                )
            ]
        )
        self.guard = guard
        self.state = ProjectState(self.root)
        self.secrets = SecretStore(guard, self.root)

    def tearDown(self):
        self.state.close()
        self.temp.cleanup()

    def test_model_capabilities_drive_vision_selection(self):
        provider = _Provider(self.guard, self.state, self.root, _Settings(), self.secrets)
        model = provider.choose_model(vision=True, prefer_json=True)
        self.assertEqual("vision-json", model.model_id)
        self.assertTrue(model.supports("vision"))
        self.assertTrue(model.supports("json_mode"))

    def test_env_key_is_never_required_on_disk(self):
        provider = _Provider(self.guard, self.state, self.root, _Settings(), self.secrets)
        with patch.dict(os.environ, {"CODECRAFT_API_KEY": "cc_test_only"}, clear=False):
            self.assertEqual("cc_test_only", provider.api_key())
            self.assertTrue(provider.has_api_key())
        self.assertFalse((self.root / ".nexvary-da" / "secrets.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI only")
    def test_windows_dpapi_roundtrip(self):
        self.secrets.set("codecraft_api_key", "cc_roundtrip_test")
        self.assertEqual("cc_roundtrip_test", self.secrets.get("codecraft_api_key"))
        payload = (self.root / ".nexvary-da" / "secrets.json").read_text(encoding="utf-8")
        self.assertNotIn("cc_roundtrip_test", payload)
        self.secrets.delete("codecraft_api_key")
        self.assertEqual("", self.secrets.get("codecraft_api_key"))

    def test_json_fence_and_scene_kind_normalization(self):
        fence = chr(96) * 3
        payload = _json_from_text(fence + "json\n" + '{"summary":"ok"}' + "\n" + fence)
        self.assertEqual("ok", payload["summary"])
        self.assertEqual(InstructionSceneKind.CASH_ON_DELIVERY, _scene_kind("cash-on-delivery"))
        self.assertEqual(InstructionSceneKind.SETUP, _scene_kind("installation"))


if __name__ == "__main__":
    unittest.main()
