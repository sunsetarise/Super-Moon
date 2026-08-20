#!/usr/bin/env python3
"""AST-based syntax and unsafe-pattern audit for additive SM34 Python."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    rows = []
    totals = {"files": 0, "lines": 0, "functions": 0, "classes": 0, "asserts": 0}
    findings = []
    for path in sorted(list((root / "src").rglob("*.py")) + list((root / "tools").glob("*.py")) + list((root / "tests").rglob("*.py"))):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        functions = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
        classes = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
        asserts = sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
        relative = path.relative_to(root).as_posix()
        rows.append({"path": relative, "lines": source.count("\n"), "functions": functions, "classes": classes, "asserts": asserts})
        totals["files"] += 1
        totals["lines"] += source.count("\n")
        totals["functions"] += functions
        totals["classes"] += classes
        totals["asserts"] += asserts
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                findings.append({"path": relative, "line": node.lineno, "finding": f"dynamic {node.func.id}"})
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        findings.append({"path": relative, "line": node.lineno, "finding": "shell=True"})
        if relative != "tools/sm34_static_audit.py":
            for token in ("TODO", "FIXME", "NotImplementedError"):
                if token in source:
                    findings.append({"path": relative, "line": None, "finding": token})
    payload = {"format": "SM34_STATIC_AUDIT_V1", "status": "PASS" if not findings else "FAIL", "totals": totals, "findings": findings, "files": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(0 if not findings else 1)


if __name__ == "__main__":
    main()
