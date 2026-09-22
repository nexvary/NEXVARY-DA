import tempfile
import unittest
from pathlib import Path

from nexvary_da.errors import PermissionDenied
from nexvary_da.file_tools import FileTools
from nexvary_da.git_tools import GitTools
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.process import ProcessRunner


class SensitivePermissionTests(unittest.TestCase):
    def test_delete_is_not_implied_by_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "x.txt").write_text("x", encoding="utf-8")
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root, {Permission.READ, Permission.WRITE}, "test"
                    )
                ]
            )
            files = FileTools(guard, root)
            with self.assertRaises(PermissionDenied):
                files.delete_file("x.txt")
            self.assertTrue((root / "x.txt").exists())

    def test_delete_permission_allows_file_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "x.txt").write_text("x", encoding="utf-8")
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root, {Permission.READ, Permission.DELETE}, "test"
                    )
                ]
            )
            FileTools(guard, root).delete_file("x.txt")
            self.assertFalse((root / "x.txt").exists())

    def test_git_push_requires_network_even_when_push_is_granted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guard = WorkspaceGuard(
                [
                    WorkspacePolicy.create(
                        root,
                        {
                            Permission.READ,
                            Permission.SHELL,
                            Permission.GIT_PUSH,
                        },
                        "test",
                    )
                ]
            )
            git = GitTools(guard, ProcessRunner(guard), root)
            with self.assertRaises(PermissionDenied):
                git.push()


if __name__ == "__main__":
    unittest.main()
