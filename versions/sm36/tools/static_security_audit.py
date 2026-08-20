#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.security import audit_source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = tuple(path for path in args.root.rglob("*.py") if "__pycache__" not in path.parts)
    findings = audit_source(paths)
    payload = {"format": "SM36_STATIC_SECURITY_AUDIT_V1", "files_scanned": len(paths), "findings": [asdict(row) for row in findings], "critical": sum(row.severity == "CRITICAL" for row in findings), "high": sum(row.severity == "HIGH" for row in findings), "passed": not findings}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if not findings else 2


if __name__ == "__main__":
    raise SystemExit(main())
