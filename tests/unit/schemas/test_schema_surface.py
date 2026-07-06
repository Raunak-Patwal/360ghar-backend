from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _is_docstring_statement(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _is_pass_only_class(node: ast.ClassDef) -> bool:
    body = node.body[1:] if node.body and _is_docstring_statement(node.body[0]) else node.body
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def test_schema_modules_do_not_define_pass_only_classes():
    offenders: list[str] = []
    for path in sorted((REPO_ROOT / "app/schemas").glob("*.py")):
        relative_path = path.relative_to(REPO_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_pass_only_class(node):
                offenders.append(f"{relative_path}:{node.lineno}:{node.name}")

    assert offenders == []
