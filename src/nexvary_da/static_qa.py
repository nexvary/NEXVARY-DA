from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True, slots=True)
class StaticCheck:
    name: str
    passed: bool
    applicable: bool
    details: str = ""


_SKIP = {".git", ".nexvary-da", ".venv", "venv", "node_modules", "build", "dist", "__pycache__"}
_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_HTML_HREF = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.IGNORECASE)
_ARABIC = re.compile(r"[\u0600-\u06FF]")


def _files(root: Path, suffix: str) -> list[Path]:
    result: list[Path] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP]
        for name in files:
            if name.lower().endswith(suffix):
                result.append(Path(current) / name)
    return sorted(result)


def check_local_links(root: str | Path) -> StaticCheck:
    base = Path(root).resolve(strict=True)
    docs = _files(base, ".md")
    broken: list[str] = []
    checked = 0
    for path in docs:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in _MD_LINK.findall(text):
            target = raw.strip().split()[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(("#", "mailto:", "tel:")):
                continue
            checked += 1
            local = unquote(parsed.path)
            if not local:
                continue
            candidate = (path.parent / local).resolve(strict=False)
            try:
                candidate.relative_to(base)
            except ValueError:
                broken.append(f"{path.relative_to(base)} -> outside workspace: {target}")
                continue
            if not candidate.exists():
                broken.append(f"{path.relative_to(base)} -> {target}")
    return StaticCheck(
        "dead_links",
        not broken,
        bool(docs),
        ("Checked " + str(checked) + " local Markdown link(s)")
        if not broken
        else "\n".join(broken[:100]),
    )


def check_orphan_html(root: str | Path) -> StaticCheck:
    base = Path(root).resolve(strict=True)
    pages = _files(base, ".html")
    if not pages:
        return StaticCheck("orphan_pages", True, False, "No HTML pages detected")
    rels = {p.relative_to(base).as_posix(): p for p in pages}
    starts = [key for key in rels if Path(key).name.lower() == "index.html"]
    if not starts:
        starts = [sorted(rels)[0]]
    graph: dict[str, set[str]] = {key: set() for key in rels}
    for rel, path in rels.items():
        text = path.read_text(encoding="utf-8", errors="replace")
        for href in _HTML_HREF.findall(text):
            parsed = urlsplit(href)
            if parsed.scheme or href.startswith(("#", "mailto:", "tel:")):
                continue
            target = (path.parent / unquote(parsed.path)).resolve(strict=False)
            try:
                target_rel = target.relative_to(base).as_posix()
            except ValueError:
                continue
            if target_rel in rels:
                graph[rel].add(target_rel)
    seen: set[str] = set()
    stack = list(starts)
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, ()))
    orphans = sorted(set(rels) - seen)
    return StaticCheck(
        "orphan_pages",
        not orphans,
        True,
        "Reachable pages: " + str(len(seen)) if not orphans else "Orphans: " + ", ".join(orphans),
    )


def check_tk_buttons(root: str | Path) -> StaticCheck:
    base = Path(root).resolve(strict=True)
    python_files = _files(base, ".py")
    seen = 0
    missing: list[str] = []
    for path in python_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError, UnicodeError):
            continue
        rel = path.relative_to(base).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name != "Button":
                continue
            seen += 1
            if not any(keyword.arg == "command" for keyword in node.keywords):
                missing.append(f"{rel}:{getattr(node, 'lineno', 0)}")
    return StaticCheck(
        "broken_buttons",
        not missing,
        bool(seen),
        f"Checked {seen} Tk Button call(s)" if not missing else "Buttons without command: " + ", ".join(missing),
    )


def _flatten_json(value, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return {prefix} if prefix else set()
    keys: set[str] = set()
    for key, child in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, dict):
            keys |= _flatten_json(child, name)
        else:
            keys.add(name)
    return keys


def check_localization(root: str | Path) -> StaticCheck:
    base = Path(root).resolve(strict=True)
    locale_dirs = [base / name for name in ("locales", "locale", "i18n", "translations") if (base / name).is_dir()]
    if not locale_dirs:
        return StaticCheck("localization", True, False, "No localization directory detected")
    json_files = sorted({p for d in locale_dirs for p in d.rglob("*.json") if p.is_file()})
    if len(json_files) < 2:
        return StaticCheck("localization", True, False, "Fewer than two JSON locale files detected")
    keysets: dict[str, set[str]] = {}
    errors: list[str] = []
    for path in json_files:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            keysets[path.relative_to(base).as_posix()] = _flatten_json(value)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(base)}: {exc}")
    if errors:
        return StaticCheck("localization", False, True, "\n".join(errors))
    union = set().union(*keysets.values())
    missing = [f"{name}: {sorted(union - keys)[:20]}" for name, keys in keysets.items() if keys != union]
    return StaticCheck("localization", not missing, True, f"{len(json_files)} locale file(s) aligned" if not missing else "\n".join(missing))


def check_rtl_signals(root: str | Path) -> StaticCheck:
    base = Path(root).resolve(strict=True)
    candidates = [*_files(base, ".py"), *_files(base, ".html"), *_files(base, ".json")]
    arabic_files: list[Path] = []
    rtl_files: set[Path] = set()
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _ARABIC.search(text):
            arabic_files.append(path)
        lowered = text.lower()
        if "rtl" in lowered or "right-to-left" in lowered or "tk.right" in lowered:
            rtl_files.add(path)
    if not arabic_files:
        return StaticCheck("rtl", True, False, "No Arabic-script UI/source strings detected")
    uncovered = [p.relative_to(base).as_posix() for p in arabic_files if p not in rtl_files]
    return StaticCheck("rtl", not uncovered, True, "RTL signal present for Arabic source files" if not uncovered else "Arabic files without RTL signal: " + ", ".join(uncovered[:50]))
