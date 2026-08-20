#!/usr/bin/env python3
"""AST audit for high-risk dynamic execution and deserialization patterns."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def call_name(node: ast.Call) -> str:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        parts = [target.attr]; value = target.value
        while isinstance(value, ast.Attribute):
            parts.append(value.attr); value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return ".".join(reversed(parts))
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    findings = []
    for path in sorted(args.root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node)
            if name in {"eval", "exec", "pickle.load", "pickle.loads", "yaml.load"}:
                findings.append({"severity": "HIGH", "path": str(path), "line": node.lineno, "pattern": name})
            if name in {"subprocess.run", "subprocess.Popen", "subprocess.call"}:
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        findings.append({"severity": "CRITICAL", "path": str(path), "line": node.lineno, "pattern": "shell=True"})
    payload = {"format": "SM35_STATIC_SECURITY_AUDIT_V1", "files_scanned": len(list(args.root.rglob("*.py"))), "findings": findings, "critical": sum(item["severity"] == "CRITICAL" for item in findings), "high": sum(item["severity"] == "HIGH" for item in findings), "passed": not findings}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
