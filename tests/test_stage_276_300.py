import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from nexvary_da.android_ui import AndroidUIHarness, parse_adb_devices, parse_uiautomator_xml
from nexvary_da.cli import build_parser
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.process import BinaryProcessResult, ProcessResult
from nexvary_da.signing_readiness import inspect_signing_readiness
from nexvary_da.state import ProjectState


XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>
<hierarchy rotation="0">
  <node text="Settings" resource-id="com.example:id/settings" class="android.widget.Button"
        content-desc="Open settings" clickable="true" enabled="true" bounds="[10,20][110,70]" />
</hierarchy>
"""


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, args, *, cwd, timeout=300, env=None):
        self.calls.append(list(args))
        if args[:2] == ["adb", "devices"]:
            return ProcessResult(list(args), 0, "List of devices attached\nemulator-5554\tdevice product:sdk model:Pixel\n", 0.01)
        if args[:3] == ["adb", "shell", "uiautomator"]:
            return ProcessResult(list(args), 0, "UI hierchary dumped", 0.01)
        if args[:3] == ["adb", "exec-out", "cat"]:
            return ProcessResult(list(args), 0, XML, 0.01)
        return ProcessResult(list(args), 0, "ok", 0.01)

    def run_bytes(self, args, *, cwd, timeout=300, env=None):
        self.calls.append(list(args))
        png = b"\x89PNG\r\n\x1a\n" + b"sample"
        return BinaryProcessResult(list(args), 0, png, 0.01)


class Stage276300Tests(unittest.TestCase):
    def test_device_parser(self):
        devices = parse_adb_devices(
            "List of devices attached\nemulator-5554\tdevice product:sdk model:Pixel\nABC\toffline\n"
        )
        self.assertEqual(2, len(devices))
        self.assertEqual("device", devices[0].state)
        self.assertEqual("offline", devices[1].state)

    def test_hierarchy_parser_and_center(self):
        nodes = parse_uiautomator_xml(XML)
        self.assertEqual(1, len(nodes))
        self.assertTrue(nodes[0].clickable)
        self.assertEqual((60, 45), nodes[0].center)

    def test_tap_label_uses_node_center(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard(
                [WorkspacePolicy.create(root, {Permission.READ, Permission.WRITE, Permission.SHELL, Permission.ADB}, "x")]
            )
            state = ProjectState(root)
            try:
                runner = FakeRunner()
                harness = AndroidUIHarness(guard, runner, state, root)
                result = harness.tap_label("settings")
                self.assertEqual(60, result["x"])
                self.assertEqual(45, result["y"])
                self.assertIn(["adb", "shell", "input", "tap", "60", "45"], runner.calls)
            finally:
                state.close()

    def test_screenshot_is_workspace_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard(
                [WorkspacePolicy.create(root, {Permission.READ, Permission.WRITE, Permission.SHELL, Permission.ADB}, "x")]
            )
            state = ProjectState(root)
            try:
                harness = AndroidUIHarness(guard, FakeRunner(), state, root)
                result = harness.screenshot()
                target = root / result["path"]
                self.assertTrue(target.is_file())
                self.assertTrue(target.read_bytes().startswith(b"\x89PNG"))
            finally:
                state.close()

    def test_signing_readiness_never_requires_secret_disclosure(self):
        with tempfile.TemporaryDirectory() as tmp:
            pfx = Path(tmp) / "certificate.pfx"
            pfx.write_bytes(b"placeholder")
            with patch.dict(
                os.environ,
                {
                    "NEXVARY_WINDOWS_SIGN_PFX": str(pfx),
                    "NEXVARY_WINDOWS_SIGN_PASSWORD": "configured",
                },
                clear=True,
            ), patch("nexvary_da.signing_readiness.shutil.which", return_value="signtool"):
                status = inspect_signing_readiness("windows")
            self.assertTrue(status.ready)
            self.assertTrue(status.credentials_present)
            self.assertNotIn("configured", str(status.to_dict()))

    def test_cli_exposes_android_ui_and_signing_status(self):
        parser = build_parser()
        android = parser.parse_args(["android-ui", ".", "--tap", "Settings"])
        signing = parser.parse_args(["signing-status", "."])
        self.assertEqual("android-ui", android.command)
        self.assertEqual(["Settings"], android.tap)
        self.assertEqual("signing-status", signing.command)



if __name__ == "__main__":
    unittest.main()
