import tempfile
import unittest
from pathlib import Path

from nexvary_da.errors import PermissionDenied, WorkspaceViolation
from nexvary_da.file_tools import FileTools
from nexvary_da.kernel import ToolContext, ToolKernel
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.state import ProjectState


class CoreTests(unittest.TestCase):
    def test_permissions_are_independent_and_outside_paths_fail(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ}, "test")])
            self.assertEqual(root.resolve(), guard.require(root, Permission.READ))
            with self.assertRaises(PermissionDenied):
                guard.require(root, Permission.WRITE)
            with self.assertRaises(WorkspaceViolation):
                guard.require(Path(outside), Permission.READ)

    def test_file_write_patch_and_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.WRITE}, "test")])
            files = FileTools(guard, root)
            files.write_text("nested/demo.txt", "alpha\nbeta\n")
            files.patch_exact("nested/demo.txt", "beta", "gamma")
            self.assertEqual("alpha\ngamma\n", files.read_text("nested/demo.txt"))
            hits = files.search("gamma", suffixes=(".txt",))
            self.assertEqual(1, len(hits))
            self.assertEqual(2, hits[0].line)

    def test_state_and_agent_events_survive_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = ProjectState(root)
            first.set_meta("branch", "dev/v0.1-core")
            first.upsert_task("T1", "Build core", "RUNNING")
            first.save_agent_slot("Builder", "builder-1", "PASS", "T1")
            first.close()
            second = ProjectState(root)
            self.assertEqual("dev/v0.1-core", second.get_meta("branch"))
            self.assertEqual("RUNNING", second.list_tasks()[0].status)
            self.assertEqual("builder-1", second.load_agent_slots()[0]["worker_id"])
            second.close()

    def test_kernel_checks_permission_before_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ}, "test")])
            state = ProjectState(root)
            called = {"value": False}
            def handler():
                called["value"] = True
            kernel = ToolKernel(guard, state)
            kernel.register("write", handler, permission=Permission.WRITE)
            with self.assertRaises(PermissionDenied):
                kernel.invoke("write", ToolContext(str(root), "qa-1"))
            self.assertFalse(called["value"])
            state.close()


if __name__ == "__main__":
    unittest.main()
