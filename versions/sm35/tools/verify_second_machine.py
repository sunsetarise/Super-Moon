#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon35.vnv import validate_reproduction


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    value = json.loads(args.receipt.read_text())
    accepted = validate_reproduction(
        value["first_machine_fingerprint"], value["second_machine_fingerprint"],
        value["first_operator_fingerprint"], value["second_operator_fingerprint"],
        value["clean_workspace"], value["output_comparison_passed"], value["evidence_ids"],
    )
    print(json.dumps({"accepted": accepted}))
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
