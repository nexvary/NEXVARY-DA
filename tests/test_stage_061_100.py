import tempfile
import unittest
from pathlib import Path

from nexvary_da.artifact_manifest import build_manifest
from nexvary_da.source_audit import audit_python_sources
from nexvary_da.static_qa import check_local_links, check_orphan_html, check_tk_buttons
from nexvary_da.workspace_health import inspect_workspace


class Stage061100Tests(unittest.TestCase):
    def test_source_audit_finds_shell_true_and_dynamic_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "x.py").write_text(
                "import subprocess\nsubprocess.run('x', shell=True)\neval('1+1')\n",
                encoding="utf-8",
            )
            codes = {finding.code for finding in audit_python_sources(root)}
            self.assertIn("shell-true", codes)
            self.assertIn("dynamic-code", codes)

    def test_markdown_link_checker_detects_missing_local_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[missing](docs/nope.md)\n", encoding="utf-8")
            result = check_local_links(root)
            self.assertTrue(result.applicable)
            self.assertFalse(result.passed)

    def test_orphan_html_graph_detects_unreachable_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text('<a href="a.html">a</a>', encoding="utf-8")
            (root / "a.html").write_text("a", encoding="utf-8")
            (root / "orphan.html").write_text("x", encoding="utf-8")
            result = check_orphan_html(root)
            self.assertFalse(result.passed)
            self.assertIn("orphan.html", result.details)

    def test_tk_button_audit_detects_missing_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ui.py").write_text("import tkinter as tk\ntk.Button(None, text='x')\n", encoding="utf-8")
            result = check_tk_buttons(root)
            self.assertTrue(result.applicable)
            self.assertFalse(result.passed)

    def test_workspace_health_detects_oversized_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.py").write_text("x" * 100, encoding="utf-8")
            result = inspect_workspace(root, max_source_bytes=10)
            self.assertIn("big.py", result.oversized_source_files)

    def test_artifact_manifest_hashes_release_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            (dist / "x.zip").write_bytes(b"abc")
            manifest = build_manifest(root)
            self.assertEqual(1, manifest["artifact_count"])
            self.assertEqual(64, len(manifest["artifacts"][0]["sha256"]))


if __name__ == "__main__":
    unittest.main()
