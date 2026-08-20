#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon35.qualification import score_release


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    decision = score_release(payload["completion"], payload["blockers"], payload["evidence_dag_valid"])
    result = {**asdict(decision), "status": decision.status.value}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if decision.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
