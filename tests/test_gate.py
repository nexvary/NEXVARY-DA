import tempfile
import unittest
from pathlib import Path

from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.process import ProcessRunner
from nexvary_da.release_gate import GateStatus, ReleaseGate
from nexvary_da.state import ProjectState


class ReleaseGateTests(unittest.TestCase):
    def test_python_gate_proves_required_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.0.0'\n")
            (root / "src" / "demo.py").write_text("VALUE = 1\n")
            (root / "tests" / "test_demo.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n"
                "    def test_ok(self): self.assertEqual(1, 1)\n"
            )
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.SHELL}, "test")])
            state = ProjectState(root)
            report = ReleaseGate(root, ProcessRunner(guard), state).run()
            required = [s for s in report.steps if s.required]
            self.assertTrue(report.ready)
            self.assertTrue(all(s.status == GateStatus.PASS for s in required))
            state.close()


if __name__ == "__main__":
    unittest.main()
