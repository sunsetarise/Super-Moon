#!/usr/bin/env python3
"""Apply the fixed SM36 quality thresholds to measured local evidence."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon36.coverage import aggregate_coverage, decide_coverage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--mutation", type=Path, required=True)
    parser.add_argument("--fuzz", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
    mutation = json.loads(args.mutation.read_text(encoding="utf-8"))
    fuzz = json.loads(args.fuzz.read_text(encoding="utf-8"))
    combined = aggregate_coverage(coverage)
    new_code = aggregate_coverage(coverage, ("/supermoon36/", "\\supermoon36\\"))
    decision = decide_coverage(
        combined, new_code, mutation_killed=mutation["killed"], mutation_total=mutation["valid_mutants"],
        fuzz_failures=fuzz["failure_count"], exclusions_valid=True,
    )
    payload = {
        "format": "SM36_LOCAL_QUALITY_DECISION_V1", **asdict(decision),
        "combined_statement_percent": combined.statement_percent,
        "combined_branch_percent": combined.branch_percent,
        "new_statement_percent": new_code.statement_percent,
        "new_branch_percent": new_code.branch_percent,
        "release_effect": "G03_TECHNICAL_THRESHOLDS_PASS_REVIEW_PENDING" if decision.passed else "G03_BLOCKED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if decision.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
