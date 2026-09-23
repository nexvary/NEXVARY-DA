from __future__ import annotations

import ast
import os
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AuditFinding:
    severity: str
    code: str
    path: str
    line: int
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_SKIP = {".git", ".nexvary-da", ".venv", "venv", "node_modules", "build", "dist", "__pycache__"}


class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str):
        self.rel = rel
        self.findings: list[AuditFinding] = []

    def add(self, node: ast.AST, severity: str, code: str, message: str) -> None:
        self.findings.append(
            AuditFinding(severity, code, self.rel, int(getattr(node, "lineno", 0) or 0), message)
        )

    def visit_Call(self, node: ast.Call) -> None:
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name in {"eval", "exec"}:
            self.add(node, "high", "dynamic-code", f"Use of {name}() requires explicit review")
        if name in {"run", "Popen", "call", "check_call", "check_output"}:
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    self.add(node, "high", "shell-true", "subprocess shell=True bypasses argv boundary")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.add(node, "medium", "bare-except", "Bare except can hide operational failures")
        self.generic_visit(node)


def audit_python_sources(root: str | Path) -> list[AuditFinding]:
    base = Path(root).resolve(strict=True)
    findings: list[AuditFinding] = []
    for current, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _SKIP]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = Path(current) / name
            rel = path.relative_to(base).as_posix()
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                source = path.read_text(encoding="utf-8", errors="strict")
                tree = ast.parse(source, filename=rel)
            except SyntaxError as exc:
                findings.append(
                    AuditFinding("critical", "syntax-error", rel, int(exc.lineno or 0), str(exc.msg))
                )
                continue
            except (OSError, UnicodeError):
                continue
            visitor = _Visitor(rel)
            visitor.visit(tree)
            findings.extend(visitor.findings)
    return findings
