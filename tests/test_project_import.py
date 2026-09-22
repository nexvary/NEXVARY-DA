import subprocess
import tempfile
import unittest
from pathlib import Path

from nexvary_da.errors import ConfigurationError, PermissionDenied
from nexvary_da.permissions import Permission
from nexvary_da.project_import import ProjectImporter


class ProjectImporterTests(unittest.TestCase):
    def test_reuses_existing_matching_clone_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp)
            repo = projects / "DemoRepo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/nexvary/DemoRepo"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "pyproject.toml").write_text(
                "[project]\nname='demo'\nversion='0.0.0'\n", encoding="utf-8"
            )

            importer = ProjectImporter(
                projects,
                {Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            imported = importer.add_from_github(
                "https://github.com/nexvary/DemoRepo",
                project_permissions={Permission.READ, Permission.SHELL},
            )
            self.assertTrue(imported.reused_existing_clone)
            self.assertEqual("python", imported.project_kind)
            self.assertTrue((projects / ".nexvary-da" / "projects.json").is_file())

    def test_new_clone_requires_network_permission_before_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp)
            importer = ProjectImporter(
                projects,
                {Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            with self.assertRaises(PermissionDenied):
                importer.add_from_github(
                    "https://github.com/nexvary/DefinitelyNotCloned",
                    project_permissions={Permission.READ},
                )

    def test_rejects_non_github_or_ambiguous_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            importer = ProjectImporter(
                Path(tmp),
                {Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            with self.assertRaises(ConfigurationError):
                importer.add_from_github(
                    "https://example.com/owner/repo",
                    project_permissions={Permission.READ},
                )


if __name__ == "__main__":
    unittest.main()
