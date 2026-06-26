"""AST lint for generated Python blocks (Pyodide-safe subset)."""

from __future__ import annotations

import ast
from typing import Any

ALLOWED_IMPORTS = frozenset({"numpy", "np", "pandas", "pd", "math", "random", "statistics"})


def lint_python_block(code: str) -> dict[str, Any]:
    code = (code or "").strip()
    if not code:
        return {"ok": False, "errors": ["empty code block"]}
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"ok": False, "errors": [f"syntax error: {exc.msg}"]}

    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    errors.append(f"import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    errors.append(f"import not allowed: {node.module}")
    return {"ok": not errors, "errors": errors}
