"""Source-security findings, trust-boundary, and SBOM validation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .contracts import ValidationError


FORBIDDEN_CALLS = {"eval", "exec", "pickle.load", "pickle.loads", "marshal.loads", "yaml.load"}


def call_name(node: ast.Call) -> str:
    target = node.func
    if isinstance(target, ast.Name):
        return target.id
    parts = []
    while isinstance(target, ast.Attribute):
        parts.append(target.attr); target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    return ".".join(reversed(parts))


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    path: str
    line: int
    pattern: str


def audit_source(paths: Iterable[Path]) -> tuple[Finding, ...]:
    findings = []
    for path in sorted(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node)
            if name in FORBIDDEN_CALLS:
                findings.append(Finding("HIGH", str(path), node.lineno, name))
            if name.startswith("subprocess."):
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        findings.append(Finding("CRITICAL", str(path), node.lineno, "shell=True"))
    return tuple(findings)


def validate_sbom(payload: Mapping[str, object]) -> bool:
    if payload.get("bomFormat") != "CycloneDX" or not payload.get("specVersion") or not isinstance(payload.get("components"), list):
        raise ValidationError("invalid SBOM envelope")
    components = payload["components"]
    identities = set()
    for row in components:
        if not isinstance(row, Mapping) or not all(row.get(key) for key in ("type", "name", "version")):
            raise ValidationError("invalid SBOM component")
        identity = (row["type"], row["name"], row["version"])
        if identity in identities:
            raise ValidationError("duplicate SBOM component")
        identities.add(identity)
    return True

