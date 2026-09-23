from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ANDROID_NS = "http://schemas.android.com/apk/res/android"
A = "{" + ANDROID_NS + "}"
_STRING_REF = re.compile(r"^@string/([A-Za-z0-9_]+)$")
_HARDCODED_ATTRS = {A + "text", A + "hint", A + "contentDescription"}


@dataclass(frozen=True, slots=True)
class AndroidQAIssue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class AndroidQAReport:
    applicable: bool
    ready: bool
    manifest: str | None
    checks: dict[str, Any]
    issues: tuple[AndroidQAIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "applicable": self.applicable,
            "ready": self.ready,
            "manifest": self.manifest,
            "checks": self.checks,
            "issues": [asdict(issue) for issue in self.issues],
        }


def _find_manifest(root: Path) -> Path | None:
    preferred = (
        root / "app" / "src" / "main" / "AndroidManifest.xml",
        root / "src" / "main" / "AndroidManifest.xml",
        root / "AndroidManifest.xml",
    )
    for path in preferred:
        if path.is_file():
            return path
    candidates = sorted(root.glob("*/src/main/AndroidManifest.xml"))
    return candidates[0] if candidates else None


def _string_file_map(res_dir: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if not res_dir.is_dir():
        return result
    for directory in sorted(res_dir.glob("values*")):
        strings = directory / "strings.xml"
        if not strings.is_file():
            continue
        try:
            tree = ET.parse(strings)
        except ET.ParseError:
            result[directory.name] = {}
            continue
        mapping: dict[str, str] = {}
        for child in tree.getroot():
            if child.tag == "string" and child.get("name"):
                mapping[str(child.get("name"))] = "".join(child.itertext()).strip()
        result[directory.name] = mapping
    return result


def audit_android_project(root: str | Path) -> AndroidQAReport:
    base = Path(root).resolve(strict=True)
    manifest = _find_manifest(base)
    if manifest is None:
        return AndroidQAReport(False, True, None, {"reason": "No AndroidManifest.xml detected"}, ())

    issues: list[AndroidQAIssue] = []
    rel_manifest = manifest.relative_to(base).as_posix()
    try:
        manifest_tree = ET.parse(manifest)
    except ET.ParseError as exc:
        issue = AndroidQAIssue("error", "manifest-xml", rel_manifest, str(exc))
        return AndroidQAReport(True, False, rel_manifest, {}, (issue,))

    manifest_root = manifest_tree.getroot()
    application = manifest_root.find("application")
    package_name = manifest_root.get("package")
    launchers = 0
    exported_missing: list[str] = []
    cleartext = False

    if application is not None:
        cleartext = application.get(A + "usesCleartextTraffic") == "true"
        for tag in ("activity", "activity-alias", "service", "receiver"):
            for component in application.findall(tag):
                filters = component.findall("intent-filter")
                if filters and component.get(A + "exported") is None:
                    name = component.get(A + "name") or "<unnamed>"
                    exported_missing.append(f"{tag}:{name}")
                if tag in {"activity", "activity-alias"}:
                    for intent_filter in filters:
                        actions = {
                            item.get(A + "name")
                            for item in intent_filter.findall("action")
                        }
                        categories = {
                            item.get(A + "name")
                            for item in intent_filter.findall("category")
                        }
                        if (
                            "android.intent.action.MAIN" in actions
                            and "android.intent.category.LAUNCHER" in categories
                        ):
                            launchers += 1

    for component in exported_missing:
        issues.append(
            AndroidQAIssue(
                "error",
                "missing-exported",
                rel_manifest,
                f"Component with intent-filter lacks android:exported: {component}",
            )
        )
    if cleartext:
        issues.append(
            AndroidQAIssue(
                "warning",
                "cleartext-traffic",
                rel_manifest,
                "android:usesCleartextTraffic=true is enabled",
            )
        )
    if launchers == 0:
        issues.append(
            AndroidQAIssue(
                "warning",
                "no-launcher",
                rel_manifest,
                "No MAIN/LAUNCHER activity was detected",
            )
        )

    source_set_root = manifest.parent
    res_dir = source_set_root / "res"
    string_maps = _string_file_map(res_dir)
    base_strings = string_maps.get("values", {})
    referenced: set[str] = set()
    hardcoded: list[tuple[str, str]] = []

    if res_dir.is_dir():
        for xml_path in sorted(res_dir.rglob("*.xml")):
            if xml_path.parent.name.startswith("values"):
                continue
            rel = xml_path.relative_to(base).as_posix()
            try:
                tree = ET.parse(xml_path)
            except ET.ParseError as exc:
                issues.append(AndroidQAIssue("error", "resource-xml", rel, str(exc)))
                continue
            for element in tree.iter():
                for attr, value in element.attrib.items():
                    match = _STRING_REF.match(value)
                    if match:
                        referenced.add(match.group(1))
                    if attr in _HARDCODED_ATTRS and value and not value.startswith("@") and not value.startswith("?"):
                        hardcoded.append((rel, value[:120]))

    missing_refs = sorted(referenced - set(base_strings))
    for name in missing_refs:
        issues.append(
            AndroidQAIssue(
                "error",
                "missing-string-resource",
                rel_manifest,
                f"Referenced @string/{name} is absent from values/strings.xml",
            )
        )

    for rel, value in hardcoded[:100]:
        issues.append(
            AndroidQAIssue(
                "warning",
                "hardcoded-ui-text",
                rel,
                f"Hardcoded Android UI text: {value}",
            )
        )

    localization_missing: dict[str, list[str]] = {}
    base_keys = set(base_strings)
    for locale, mapping in string_maps.items():
        if locale == "values":
            continue
        missing = sorted(base_keys - set(mapping))
        if missing:
            localization_missing[locale] = missing[:100]
            issues.append(
                AndroidQAIssue(
                    "warning",
                    "localization-incomplete",
                    (res_dir / locale / "strings.xml").relative_to(base).as_posix(),
                    f"{len(missing)} base string(s) are missing from {locale}",
                )
            )

    ready = not any(issue.severity == "error" for issue in issues)
    checks = {
        "package": package_name,
        "launcher_count": launchers,
        "cleartext_traffic": cleartext,
        "base_string_count": len(base_strings),
        "referenced_string_count": len(referenced),
        "missing_string_references": missing_refs,
        "hardcoded_ui_text_count": len(hardcoded),
        "locale_count": max(0, len(string_maps) - (1 if "values" in string_maps else 0)),
        "localization_missing": localization_missing,
    }
    return AndroidQAReport(True, ready, rel_manifest, checks, tuple(issues))
