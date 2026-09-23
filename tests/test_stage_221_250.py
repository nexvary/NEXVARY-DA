import tempfile
import unittest
from pathlib import Path

from nexvary_da.android_qa import audit_android_project
from nexvary_da.cli import build_parser
from nexvary_da.doctor import run_project_doctor
from nexvary_da.permissions import Permission
from nexvary_da.project import ProjectRuntime, init_project
from nexvary_da.provenance import source_manifest, verify_source_manifest


MANIFEST = """<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.app">
<application>
  <activity android:name=".MainActivity">
    <intent-filter>
      <action android:name="android.intent.action.MAIN"/>
      <category android:name="android.intent.category.LAUNCHER"/>
    </intent-filter>
  </activity>
</application>
</manifest>
"""


class Stage221250Tests(unittest.TestCase):
    def test_android_qa_detects_missing_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "app" / "src" / "main" / "AndroidManifest.xml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(MANIFEST, encoding="utf-8")
            report = audit_android_project(root)
            self.assertTrue(report.applicable)
            self.assertFalse(report.ready)
            self.assertIn("missing-exported", {issue.code for issue in report.issues})

    def test_android_qa_validates_string_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "app" / "src" / "main" / "AndroidManifest.xml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                MANIFEST.replace(
                    '<activity android:name=".MainActivity">',
                    '<activity android:name=".MainActivity" android:exported="true">',
                ),
                encoding="utf-8",
            )
            res = root / "app" / "src" / "main" / "res"
            (res / "values").mkdir(parents=True)
            (res / "layout").mkdir(parents=True)
            (res / "values" / "strings.xml").write_text(
                '<resources><string name="app_name">App</string></resources>',
                encoding="utf-8",
            )
            (res / "layout" / "main.xml").write_text(
                '<TextView xmlns:android="http://schemas.android.com/apk/res/android" android:text="@string/missing"/>',
                encoding="utf-8",
            )
            report = audit_android_project(root)
            self.assertFalse(report.ready)
            self.assertIn(
                "missing-string-resource",
                {issue.code for issue in report.issues},
            )

    def test_source_manifest_is_deterministic_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("VALUE = 1\n", encoding="utf-8")
            first = source_manifest(root)
            second = source_manifest(root)
            self.assertEqual(first["source_root_sha256"], second["source_root_sha256"])
            (root / "a.py").write_text("VALUE = 2\n", encoding="utf-8")
            verified = verify_source_manifest(root, first)
            self.assertFalse(verified["match"])

    def test_provenance_internal_state_is_not_in_source_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x=1\n", encoding="utf-8")
            internal = root / ".nexvary-da"
            internal.mkdir()
            (internal / "private.py").write_text("secret=1\n", encoding="utf-8")
            manifest = source_manifest(root)
            paths = {item["path"] for item in manifest["files"]}
            self.assertIn("a.py", paths)
            self.assertNotIn(".nexvary-da/private.py", paths)

    def test_doctor_and_new_cli_commands_are_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project]\nname='doctor-test'\nversion='0'\n",
                encoding="utf-8",
            )
            init_project(
                root,
                name="doctor-test",
                permissions={Permission.READ, Permission.WRITE, Permission.SHELL},
            )
            runtime = ProjectRuntime(root)
            try:
                result = run_project_doctor(runtime)
                self.assertIn(result["overall"], {"PASS", "FAIL"})
                self.assertIn("state_database", {item["name"] for item in result["checks"]})
            finally:
                runtime.close()

            parser = build_parser()
            self.assertEqual(
                "checkpoint",
                parser.parse_args(["checkpoint", str(root)]).command,
            )
            self.assertEqual(
                "resume-context",
                parser.parse_args(["resume-context", str(root)]).command,
            )
            self.assertEqual(
                "provenance",
                parser.parse_args(["provenance", str(root)]).command,
            )


if __name__ == "__main__":
    unittest.main()
