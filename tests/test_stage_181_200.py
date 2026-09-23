import tempfile
import unittest
from pathlib import Path

from nexvary_da.orchestration import ExecutionPlan, PlanStep
from nexvary_da.permissions import Permission
from nexvary_da.plan_execution import PlanExecutionManager
from nexvary_da.project import ProjectRuntime, init_project


class Stage181200Tests(unittest.TestCase):
    def _runtime(self, root: Path, permissions):
        (root / "pyproject.toml").write_text(
            "[project]\nname='x'\nversion='0'\n",
            encoding="utf-8",
        )
        (root / "hello.txt").write_text("alpha\n", encoding="utf-8")
        init_project(root, name="x", permissions=set(permissions))
        return ProjectRuntime(root)

    def test_read_only_plan_is_accepted_and_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(
                Path(tmp),
                {Permission.READ, Permission.SHELL},
            )
            try:
                plan = ExecutionPlan(
                    (PlanStep("read_text", {"path": "hello.txt"}, "inspect"),),
                    "read",
                )
                receipt = PlanExecutionManager(runtime).execute(
                    plan,
                    dry_run=False,
                )
                self.assertTrue(receipt.accepted)
                self.assertTrue(receipt.executed)
                self.assertEqual("alpha\n", receipt.results[0]["output"])
            finally:
                runtime.close()

    def test_write_is_blocked_without_explicit_mutation_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(
                Path(tmp),
                {Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            try:
                plan = ExecutionPlan(
                    (PlanStep("write_text", {"path": "out.txt", "content": "x"}, "write"),),
                    "write",
                )
                receipt = PlanExecutionManager(runtime).execute(
                    plan,
                    approve_mutations=False,
                    dry_run=False,
                )
                self.assertFalse(receipt.accepted)
                self.assertFalse((Path(tmp) / "out.txt").exists())
                self.assertEqual(
                    "mutation-not-approved",
                    receipt.review["issues"][0]["code"],
                )
            finally:
                runtime.close()

    def test_approved_write_still_requires_workspace_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(
                Path(tmp),
                {Permission.READ, Permission.SHELL},
            )
            try:
                plan = ExecutionPlan(
                    (PlanStep("write_text", {"path": "out.txt", "content": "x"}, "write"),),
                    "write",
                )
                review = PlanExecutionManager(runtime).review(
                    plan,
                    approve_mutations=True,
                )
                self.assertFalse(review["accepted"])
                codes = {issue["code"] for issue in review["issues"]}
                self.assertIn("permission-not-granted", codes)
            finally:
                runtime.close()

    def test_unknown_tool_is_never_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(
                Path(tmp),
                {Permission.READ, Permission.SHELL},
            )
            try:
                plan = ExecutionPlan(
                    (PlanStep("magic.root.shell", {}, "no"),),
                    "unknown",
                )
                review = PlanExecutionManager(runtime).review(plan)
                self.assertFalse(review["accepted"])
                self.assertEqual("unknown-tool", review["issues"][0]["code"])
            finally:
                runtime.close()

    def test_dry_run_does_not_mutate_even_when_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(
                Path(tmp),
                {Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            try:
                plan = ExecutionPlan(
                    (PlanStep("write_text", {"path": "out.txt", "content": "x"}, "write"),),
                    "write",
                )
                receipt = PlanExecutionManager(runtime).execute(
                    plan,
                    approve_mutations=True,
                    dry_run=True,
                )
                self.assertTrue(receipt.accepted)
                self.assertFalse(receipt.executed)
                self.assertFalse((Path(tmp) / "out.txt").exists())
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
