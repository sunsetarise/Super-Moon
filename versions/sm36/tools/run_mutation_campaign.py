#!/usr/bin/env python3
"""Run a reproducible first-order source mutation campaign against SM36 tests."""

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
    ("contracts.py", 'self.size_bytes < 0', 'self.size_bytes <= 0'),
    ("contracts.py", 'if end < start:\n            raise ValidationError("methodology result ends before it starts")', 'if end <= start:\n            raise ValidationError("methodology result ends before it starts")'),
    ("coverage.py", 'self.covered_statements > self.statements', 'self.covered_statements < self.statements'),
    ("coverage.py", 'mutation_total <= 0', 'mutation_total < 0'),
    ("coverage.py", 'return len(independently_demonstrated) == width', 'return len(independently_demonstrated) != width'),
    ("coverage.py", 'fuzz_pass = fuzz_failures == 0', 'fuzz_pass = fuzz_failures != 0'),
    ("framing.py", 'if path in seen:', 'if False and path in seen:'),
    ("hpc.py", '0 <= self.relative_residual <= 1e-8', '1e-8 <= self.relative_residual <= 1'),
    ("methodology.py", 'if record.phase_id in PHYSICAL_PHASES:', 'if record.phase_id not in PHYSICAL_PHASES:'),
    ("physical.py", 'self.sanitizer_errors == 0', 'self.sanitizer_errors >= 0'),
    ("qualification.py", 'gates[key].state is not ResultState.PASS', 'gates[key].state is ResultState.PASS'),
    ("registry.py", 'if len(rows) != 15000:', 'if len(rows) == 15000:'),
    ("security.py", 'if name in FORBIDDEN_CALLS:', 'if False and name in FORBIDDEN_CALLS:'),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--extra-pythonpath", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory(prefix="sm36-mutation-") as directory:
        root = Path(directory)
        for index, (filename, old, new) in enumerate(MUTANTS, 1):
            mutant_src = root / f"mutant-{index:02d}"
            shutil.copytree(args.src, mutant_src)
            target = mutant_src / "supermoon36" / filename
            text = target.read_text(encoding="utf-8")
            occurrences = text.count(old)
            if occurrences != 1:
                rows.append({"id": index, "file": filename, "status": "INVALID", "occurrences": occurrences})
                continue
            target.write_text(text.replace(old, new, 1), encoding="utf-8")
            environment = dict(os.environ)
            pythonpath = [str(mutant_src), *args.extra_pythonpath]
            environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
            run = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(args.tests), "-p", "test_*.py"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment, timeout=180,
            )
            rows.append({"id": index, "file": filename, "operator": f"{old} -> {new}", "status": "KILLED" if run.returncode else "SURVIVED", "test_exit_code": run.returncode})
    valid = [row for row in rows if row["status"] != "INVALID"]
    killed = sum(row["status"] == "KILLED" for row in valid)
    score = 100.0 * killed / len(valid) if valid else 0.0
    payload = {
        "format": "SM36_MUTATION_CAMPAIGN_V1", "mutants": rows, "valid_mutants": len(valid),
        "killed": killed, "survived": sum(row["status"] == "SURVIVED" for row in valid),
        "score_percent": score, "passed": len(valid) == len(MUTANTS) and score >= 90.0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
