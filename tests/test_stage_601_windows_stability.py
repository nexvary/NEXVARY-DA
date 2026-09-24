from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nexvary_da.permissions import Permission
from nexvary_da.project import ProjectRuntime, init_project
from nexvary_da.subprocess_policy import hidden_window_kwargs
from nexvary_da.ui_theme import scale_for_screen


class WindowsStabilityTests(unittest.TestCase):
    def test_hidden_process_policy_is_platform_safe(self):
        kwargs = hidden_window_kwargs()
        if os.name == "nt":
            self.assertIn("startupinfo", kwargs)
            self.assertNotEqual(kwargs.get("creationflags", 0), 0)
        else:
            self.assertEqual(kwargs, {})

    def test_non_git_workspace_does_not_spawn_git_during_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_project(
                root,
                name="Stability Smoke",
                permissions={Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            runtime = ProjectRuntime(root)
            try:
                with mock.patch.object(
                    runtime.runner,
                    "run",
                    side_effect=AssertionError("git subprocess must not run for non-git workspace"),
                ):
                    self.assertFalse(runtime.git.is_repository())
                    self.assertIsNone(runtime.git.branch())
                    self.assertIsNone(runtime.git.commit())
                    self.assertEqual(runtime.git.changed_files(), [])
            finally:
                runtime.close()

    def test_laptop_resolution_uses_compact_scale(self):
        self.assertEqual(scale_for_screen(1366, 768), 0.92)


if __name__ == "__main__":
    unittest.main()
