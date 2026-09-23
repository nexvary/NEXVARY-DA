import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.cua_adapter import CuaDriverAdapter
from nexvary_da.fastmcp_gateway import FastMCPGateway
from nexvary_da.media_adapters import MoneyPrinterTurboAdapter, VoiceStudioAdapter
from nexvary_da.oya_adapter import OyaBrowserAdapter
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.plugin_hub import PluginHub
from nexvary_da.process import ProcessResult
from nexvary_da.state import ProjectState


class FakeRunner:
    def __init__(self, output='{"ok":true}'):
        self.output = output
        self.calls = []

    def run(self, args, *, cwd, timeout=300, env=None):
        self.calls.append((list(args), str(cwd), timeout, dict(env or {})))
        return ProcessResult(list(args), 0, self.output, 0.01)


class FakeProcesses:
    def __init__(self):
        self.calls = []

    def start(self, args, *, cwd):
        self.calls.append((list(args), str(cwd)))

        class Item:
            process_id = "p-1"
            pid = 123

        return Item()


def guard_for(root: Path, *permissions: Permission) -> WorkspaceGuard:
    return WorkspaceGuard(
        [WorkspacePolicy.create(root, {Permission.READ, *permissions}, "test")]
    )


class Stage301350Tests(unittest.TestCase):
    def test_plugin_hub_has_six_guarded_integrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = ProjectState(root)
            try:
                hub = PluginHub(guard_for(root), state, root)
                items = {item.plugin_id: item for item in hub.all_statuses()}
                self.assertEqual(
                    {
                        "fastmcp",
                        "cua-driver",
                        "oya-browser",
                        "voicestudio",
                        "qwen-image-2.1",
                        "moneyprinterturbo",
                    },
                    set(items),
                )
                self.assertIn("Qwen Research License", items["qwen-image-2.1"].license)
                snapshot = json.dumps(hub.snapshot())
                key = os.environ.get("OYA_API_KEY", "")
                if key:
                    self.assertNotIn(key, snapshot)
            finally:
                state.close()

    def test_cua_requires_explicit_mutation_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "cua-driver"
            fake.write_text("placeholder", encoding="utf-8")
            state = ProjectState(root)
            runner = FakeRunner('{"apps":[]}')
            guard = guard_for(
                root,
                Permission.SHELL,
                Permission.WRITE,
                Permission.DESKTOP_AUTOMATION,
            )
            try:
                with patch.dict(os.environ, {"NEXVARY_DA_CUA_BIN": str(fake)}, clear=False):
                    adapter = CuaDriverAdapter(guard, runner, state, root)
                    with self.assertRaises(PermissionError):
                        adapter.call("click", {"x": 1, "y": 2})
                    result = adapter.call("list_apps", {})
                self.assertEqual(0, result["returncode"])
                self.assertEqual("list_apps", runner.calls[0][0][2])
            finally:
                state.close()

    def test_fastmcp_remote_bind_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            server = root / "server.py"
            server.write_text("mcp = object()\n", encoding="utf-8")
            fake = root / "fastmcp"
            fake.write_text("placeholder", encoding="utf-8")
            state = ProjectState(root)
            guard = guard_for(root, Permission.SHELL, Permission.NETWORK)
            try:
                with patch.dict(os.environ, {"NEXVARY_DA_FASTMCP_BIN": str(fake)}, clear=False):
                    gateway = FastMCPGateway(guard, FakeRunner(), FakeProcesses(), state, root)
                    with self.assertRaises(PermissionError):
                        gateway.start(
                            "server.py",
                            transport="http",
                            host="0.0.0.0",
                            allow_remote_bind=False,
                        )
            finally:
                state.close()

    def test_oya_rejects_plain_http_remote_site(self):
        with self.assertRaises(ValueError):
            OyaBrowserAdapter._validate_url("http://example.com")
        self.assertEqual(
            "http://127.0.0.1:8000",
            OyaBrowserAdapter._validate_url("http://127.0.0.1:8000"),
        )

    def test_voicestudio_rejects_non_loopback_plain_http(self):
        VoiceStudioAdapter._validate_base("http://127.0.0.1:3900")
        with self.assertRaises(ValueError):
            VoiceStudioAdapter._validate_base("http://example.com:3900")

    def test_moneyprinter_root_must_remain_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            other = Path(outside)
            (other / "cli.py").write_text("print('x')\n", encoding="utf-8")
            state = ProjectState(root)
            try:
                adapter = MoneyPrinterTurboAdapter(
                    guard_for(root, Permission.SHELL, Permission.NETWORK),
                    FakeRunner(),
                    state,
                    root,
                )
                with patch.dict(
                    os.environ,
                    {"NEXVARY_DA_MONEYPRINTER_ROOT": str(other)},
                    clear=False,
                ):
                    self.assertFalse(adapter.status().available)
            finally:
                state.close()


if __name__ == "__main__":
    unittest.main()
