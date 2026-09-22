import tempfile
import unittest
from pathlib import Path

from nexvary_da.coordinator import DevelopmentCoordinator
from nexvary_da.modes import WorkMode
from nexvary_da.permissions import Permission
from nexvary_da.project import ProjectRuntime, init_project


class CoordinatorTests(unittest.TestCase):
    def _project(self, root: Path) -> None:
        (root / "src").mkdir()
        (root / "tests").mkdir()
        (root / "pyproject.toml").write_text(
            "[project]\nname='coordinator-test'\nversion='0.0.0'\n",
            encoding="utf-8",
        )
        (root / "src" / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests" / "test_demo.py").write_text(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self): self.assertEqual(1, 1)\n",
            encoding="utf-8",
        )
        init_project(
            root,
            name="coordinator-test",
            permissions={Permission.READ, Permission.SHELL, Permission.RELEASE},
        )

    def test_fast_runs_build_without_qa_or_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            runtime = ProjectRuntime(root)
            try:
                report = DevelopmentCoordinator(runtime).run(WorkMode.FAST)
                self.assertTrue(report.complete)
                self.assertIsNotNone(report.build)
                self.assertIsNone(report.qa)
                self.assertIsNone(report.release_gate)
            finally:
                runtime.close()

    def test_engineer_runs_build_and_qa_without_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            runtime = ProjectRuntime(root)
            try:
                report = DevelopmentCoordinator(runtime).run(WorkMode.ENGINEER)
                self.assertTrue(report.complete)
                self.assertTrue(report.build["success"])
                self.assertTrue(report.qa["success"])
                self.assertIsNone(report.release_gate)
            finally:
                runtime.close()

    def test_release_refuses_ready_when_heavy_adapters_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            runtime = ProjectRuntime(root)
            try:
                report = DevelopmentCoordinator(runtime).run(WorkMode.RELEASE)
                self.assertFalse(report.complete)
                self.assertFalse(report.release_gate["ready"])
                missing = {
                    step["name"]
                    for step in report.release_gate["steps"]
                    if step["status"] == "NOT_CONFIGURED"
                }
                self.assertIn("ui_gate", missing)
                self.assertIn("artifact_validation", missing)
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
