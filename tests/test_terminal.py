import sys
import tempfile
import unittest
from pathlib import Path

from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.terminal import PersistentTerminal


class PersistentTerminalTests(unittest.TestCase):
    def test_working_directory_persists_between_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            child.mkdir()
            guard = WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, Permission.SHELL}, "test")])
            with PersistentTerminal(guard, root) as terminal:
                first = terminal.run(f'cd "{child}"')
                self.assertEqual(0, first.returncode)
                command = f'"{sys.executable}" -c "import os; print(os.path.basename(os.getcwd()))"'
                second = terminal.run(command)
                self.assertEqual(0, second.returncode)
                self.assertIn("child", second.output)


if __name__ == "__main__":
    unittest.main()
