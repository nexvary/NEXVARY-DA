import tempfile
import unittest
from pathlib import Path

from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.process import ProcessRunner
from nexvary_da.release_gate import GateStatus, ReleaseGate
from nexvary_da.state import ProjectState


class Stage141180Tests(unittest.TestCase):
    def test_state_recent_events_and_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ProjectState(Path(tmp))
            for index in range(8):
                state.record_event("demo", {"index": index})
            recent = state.list_events(limit=3)
            self.assertEqual(3, len(recent))
            self.assertEqual(7, recent[0]["payload"]["index"])
            removed = state.prune_events(keep=2)
            self.assertGreaterEqual(removed, 6)
            self.assertEqual(2, len(state.list_events(limit=20)))
            state.close()

    def test_strict_gate_uses_real_static_analysis_and_stays_fail_closed_on_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n", encoding="utf-8")
            (root / "src" / "bad.py").write_text("VALUE = eval('1+1')\n", encoding="utf-8")
            (root / "tests" / "test_ok.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.SHELL}, "t")])
            state = ProjectState(root)
            report = ReleaseGate(root, ProcessRunner(guard), state).run(strict=True)
            steps = {step.name: step for step in report.steps}
            self.assertEqual(GateStatus.FAIL, steps["static_analysis"].status)
            self.assertEqual(GateStatus.NOT_CONFIGURED, steps["ui_gate"].status)
            self.assertFalse(report.ready)
            state.close()

    def test_non_strict_gate_keeps_optional_ui_checks_non_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n", encoding="utf-8")
            (root / "src" / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / "tests" / "test_ok.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.SHELL}, "t")])
            state = ProjectState(root)
            report = ReleaseGate(root, ProcessRunner(guard), state).run(strict=False)
            self.assertTrue(report.ready)
            state.close()


if __name__ == "__main__":
    unittest.main()
