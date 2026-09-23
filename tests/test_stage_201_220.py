import tempfile
import unittest
from pathlib import Path

from nexvary_da.checkpoint import CheckpointStore
from nexvary_da.permissions import Permission
from nexvary_da.project import ProjectRuntime, init_project
from nexvary_da.redaction import redact


class Stage201220Tests(unittest.TestCase):
    def _runtime(self, root: Path):
        (root / "pyproject.toml").write_text(
            "[project]\nname='resume-test'\nversion='0'\n",
            encoding="utf-8",
        )
        init_project(
            root,
            name="resume-test",
            permissions={Permission.READ, Permission.WRITE, Permission.SHELL},
        )
        return ProjectRuntime(root)

    def test_redaction_hides_sensitive_keys_and_authorization_text(self):
        value = redact(
            {
                "password": "sample-value",
                "nested": {"authorization": "sample-auth"},
                "text": "Bearer samplevalue12345",
            }
        )
        self.assertEqual("[REDACTED]", value["password"])
        self.assertEqual("[REDACTED]", value["nested"]["authorization"])
        self.assertNotIn("samplevalue12345", value["text"])

    def test_checkpoint_create_load_and_compact_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            try:
                (root / "new.txt").write_text("hello", encoding="utf-8")
                store = CheckpointStore(runtime)
                created = store.create(label="before-refactor", note="safe note")
                loaded = store.load(created["checkpoint_id"])
                self.assertEqual(created["checkpoint_id"], loaded["checkpoint_id"])
                self.assertEqual("before-refactor", loaded["label"])
                compact = store.compact_resume()
                self.assertEqual(
                    created["checkpoint_id"],
                    compact["latest_checkpoint"]["checkpoint_id"],
                )
                self.assertIn("permissions", compact["current"])
            finally:
                runtime.close()

    def test_checkpoint_prune_keeps_requested_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            try:
                store = CheckpointStore(runtime)
                for index in range(4):
                    store.create(label=f"cp-{index}")
                removed = store.prune(keep=2)
                self.assertEqual(2, removed)
                self.assertEqual(2, len(store.list(limit=20)))
            finally:
                runtime.close()

    def test_checkpoint_id_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = self._runtime(root)
            try:
                store = CheckpointStore(runtime)
                with self.assertRaises(ValueError):
                    store.load("../../outside")
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
