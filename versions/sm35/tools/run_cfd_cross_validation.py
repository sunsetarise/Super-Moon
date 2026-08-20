#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon35.vnv import NeutralCFDCase, compare_cfd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case_payload = json.loads(args.case.read_text())
    case_payload["axes"] = tuple(case_payload["axes"])
    case_payload["moment_center_m"] = tuple(case_payload["moment_center_m"])
    case_payload["quantities"] = tuple(case_payload["quantities"])
    result = compare_cfd(NeutralCFDCase(**case_payload), json.loads(args.first.read_text()), json.loads(args.second.read_text()))
    args.output.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    return 0 if result.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
