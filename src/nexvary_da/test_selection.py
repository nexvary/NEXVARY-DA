from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .environment import detect_project_kind


@dataclass(frozen=True, slots=True)
class TestSelection:
    project_kind: str
    commands: tuple[tuple[str, ...], ...]
    candidates: tuple[str, ...]
    full_suite: bool
    rationale: str


def select_tests(root: str | Path, changed_files: list[str] | tuple[str, ...]) -> TestSelection:
    base = Path(root)
    kind = detect_project_kind(base)
    changed = tuple(sorted(set(changed_files)))

    if kind == "python":
        tests = base / "tests"
        candidates: set[str] = set()
        for rel in changed:
            path = Path(rel)
            if path.parts and path.parts[0] == "tests" and path.suffix == ".py":
                candidates.add(rel)
            elif path.suffix == ".py" and path.name != "__init__.py":
                expected = tests / f"test_{path.stem}.py"
                if expected.is_file():
                    candidates.add(expected.relative_to(base).as_posix())
        if candidates:
            modules = tuple(
                candidate[:-3].replace("/", ".").replace("\\", ".")
                for candidate in sorted(candidates)
            )
            return TestSelection(
                kind,
                (("python", "-m", "unittest", *modules, "-v"),),
                tuple(sorted(candidates)),
                False,
                "Selected Python tests with direct filename affinity to changed sources.",
            )
        return TestSelection(
            kind,
            (("python", "-m", "unittest", "discover", "-s", "tests", "-v"),),
            (),
            True,
            "No safe direct test mapping found; use the full Python test suite.",
        )

    if kind == "gradle":
        modules = sorted({
            Path(rel).parts[0]
            for rel in changed
            if len(Path(rel).parts) > 1 and (base / Path(rel).parts[0] / "build.gradle").exists()
        })
        commands = tuple((f":{module}:test",) for module in modules)
        return TestSelection(
            kind,
            commands if commands else (("test",),),
            tuple(modules),
            not bool(modules),
            "Use module-local Gradle tests when a module boundary is unambiguous.",
        )

    if kind == "node":
        candidates = tuple(
            rel for rel in changed
            if ".test." in rel or ".spec." in rel or rel.startswith("test/") or rel.startswith("tests/")
        )
        return TestSelection(
            kind,
            (("npm", "test", "--", *candidates),) if candidates else (("npm", "test"),),
            candidates,
            not bool(candidates),
            "Pass changed test files to the Node test script when available.",
        )

    if kind == "cmake":
        return TestSelection(
            kind,
            (("ctest", "--test-dir", "build", "--output-on-failure"),),
            (),
            True,
            "CTest does not provide a portable source-to-test mapping; use configured suite.",
        )

    return TestSelection(kind, (), (), True, "No supported test selection profile.")
