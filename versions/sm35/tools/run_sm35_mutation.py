#!/usr/bin/env python3
"""Deterministic first-order mutation campaign for SM35 safety-critical logic."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


MUTANTS = (
    ("qualification.py", "score >= 95.0", "score >= 101.0", "M001_score_threshold"),
    ("qualification.py", "and not open_blockers and evidence_dag_valid", "and evidence_dag_valid", "M002_ignore_blockers"),
    ("qualification.py", "and not open_blockers and evidence_dag_valid", "and not open_blockers", "M003_ignore_dag"),
    ("qualification.py", "0.0 <= value <= 1.0", "-1.0 <= value <= 2.0", "M004_fraction_bounds"),
    ("coverage_gate.py", "statement_percent >= statement_threshold and branch_percent >= branch_threshold", "statement_percent >= statement_threshold or branch_percent >= branch_threshold", "M005_coverage_or"),
    ("coverage_gate.py", "100.0 if total == 0", "0.0 if total == 0", "M006_empty_coverage"),
    ("contracts.py", "if self.status is ExecutionStatus.PASS:", "if False and self.status is ExecutionStatus.PASS:", "M007_pass_evidence_bypass"),
    ("contracts.py", "len(artifact_ids) != len(set(artifact_ids))", "len(artifact_ids) == len(set(artifact_ids))", "M008_duplicate_artifacts"),
    ("contracts.py", "self.reviewer_decision is not ExecutionStatus.PASS", "False", "M009_reviewer_bypass"),
    ("vnv.py", "elapsed_seconds >= profile_hours * 3600", "elapsed_seconds > profile_hours * 3600", "M010_endurance_duration"),
    ("vnv.py", "first_machine != second_machine", "first_machine == second_machine", "M011_machine_independence"),
    ("framing.py", "if path in seen:", "if False and path in seen:", "M012_duplicate_frames"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--sm34-src", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for filename, old, new, mutant_id in MUTANTS:
            target_tree = root / mutant_id
            shutil.copytree(args.tree / "src", target_tree / "src")
            source = target_tree / "src" / "supermoon35" / filename
            text = source.read_text(encoding="utf-8")
            if text.count(old) != 1:
                raise RuntimeError(f"{mutant_id} target count is {text.count(old)}")
            source.write_text(text.replace(old, new), encoding="utf-8")
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join((str(target_tree / "src"), str(args.sm34_src)))
            run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(args.tree / "tests"), "-p", "test*.py"],
                env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False,
            )
            results.append({"mutant_id": mutant_id, "file": filename, "killed": run.returncode != 0, "returncode": run.returncode})
    killed = sum(item["killed"] for item in results)
    score = 100.0 * killed / len(results)
    payload = {"format": "SM35_MUTATION_RESULTS_V1", "tool": "deterministic-source-replacement", "mutants": results, "killed": killed, "total": len(results), "score_percent": score, "threshold_percent": 85.0, "passed": score >= 85.0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
