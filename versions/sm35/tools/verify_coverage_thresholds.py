#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("--statement", type=float, default=95.0)
    parser.add_argument("--branch", type=float, default=90.0)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(source))
    from supermoon35.coverage_gate import verify_coverage

    payload = json.loads(args.coverage_json.read_text(encoding="utf-8"))
    decision = verify_coverage(payload, statement_threshold=args.statement, branch_threshold=args.branch)
    print(json.dumps(asdict(decision), sort_keys=True))
    return 0 if decision.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
