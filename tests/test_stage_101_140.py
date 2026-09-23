import io
import json
import tempfile
import unittest
from pathlib import Path

from nexvary_da.android_profile import AndroidTools
from nexvary_da.github_client import GitHubRESTClient
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.process import ProcessResult
from nexvary_da.release_policy import ReleasePolicy


class FakeResponse:
    def __init__(self, value):
        self.value = value
    def read(self):
        return json.dumps(self.value).encode("utf-8")


class FakeRunner:
    def __init__(self):
        self.calls = []
    def run(self, args, *, cwd, timeout=300, env=None):
        self.calls.append((list(args), str(cwd), timeout))
        return ProcessResult(list(args), 0, "ok", 0.01)


class Stage101140Tests(unittest.TestCase):
    def test_github_reads_require_network_and_parse_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.NETWORK}, "x")])
            urls = []
            def opener(request, timeout=60):
                urls.append(request.full_url)
                return FakeResponse({"workflow_runs": [{"id": 1}]})
            client = GitHubRESTClient(guard, str(root), "https://github.com/nexvary/NEXVARY-DA", urlopen=opener)
            runs = client.workflow_runs(branch="dev/v0.1-core")
            self.assertEqual(1, runs[0]["id"])
            self.assertIn("actions/runs", urls[0])

    def test_draft_release_requires_release_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.NETWORK}, "x")])
            client = GitHubRESTClient(guard, str(root), "https://github.com/a/b", urlopen=lambda *a, **k: FakeResponse({}))
            with self.assertRaises(Exception):
                client.create_draft_release("v1", "v1")

    def test_android_adb_requires_independent_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.SHELL}, "x")])
            android = AndroidTools(guard, FakeRunner(), root)
            with self.assertRaises(Exception):
                android.devices()

    def test_android_install_stays_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apk = root / "app.apk"
            apk.write_bytes(b"x")
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.SHELL, Permission.ADB}, "x")])
            runner = FakeRunner()
            android = AndroidTools(guard, runner, root)
            result = android.install_apk("app.apk")
            self.assertEqual(0, result.returncode)
            self.assertEqual("adb", runner.calls[0][0][0])

    def test_release_policy_auto_required_semantics(self):
        policy = ReleasePolicy(dead_links="auto", rtl="required", localization="disabled")
        self.assertFalse(policy.required("dead_links", applicable=False))
        self.assertTrue(policy.required("dead_links", applicable=True))
        self.assertTrue(policy.required("rtl", applicable=False))
        self.assertFalse(policy.required("localization", applicable=True))


if __name__ == "__main__":
    unittest.main()
