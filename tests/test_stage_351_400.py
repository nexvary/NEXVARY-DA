import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.integration_settings import IntegrationSettings
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy


def guard_for(root: Path, *permissions: Permission) -> WorkspaceGuard:
    return WorkspaceGuard(
        [WorkspacePolicy.create(root, {Permission.READ, *permissions}, "test")]
    )


class UsabilitySettingsTests(unittest.TestCase):
    def test_non_secret_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = IntegrationSettings(
                guard_for(root, Permission.WRITE),
                root,
            )
            saved = store.save(
                {
                    "cua_bin": "tools/cua-driver",
                    "voicestudio_url": "http://127.0.0.1:3900",
                    "qwen_device": "cpu",
                }
            )
            self.assertEqual("tools/cua-driver", saved["cua_bin"])
            self.assertEqual("cpu", store.load()["qwen_device"])
            raw = json.loads((root / ".nexvary-da" / "integrations.json").read_text())
            self.assertNotIn("api_key", " ".join(raw.keys()).lower())

    def test_environment_overrides_saved_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = IntegrationSettings(
                guard_for(root, Permission.WRITE),
                root,
            )
            store.save({"cua_bin": "saved"})
            with patch.dict(os.environ, {"NEXVARY_DA_CUA_BIN": "managed"}, clear=False):
                self.assertEqual(
                    "managed",
                    store.get("cua_bin", "NEXVARY_DA_CUA_BIN", ""),
                )

    def test_secret_like_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = IntegrationSettings(
                guard_for(root, Permission.WRITE),
                root,
            )
            with self.assertRaises(KeyError):
                store.save({"oya_api_key": "secret"})


if __name__ == "__main__":
    unittest.main()
