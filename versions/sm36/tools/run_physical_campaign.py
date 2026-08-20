#!/usr/bin/env python3
"""Authorized orchestrator for inherited real-backend qualification drivers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


DRIVERS = {
    "petsc_mpi": "run_petsc_rank_matrix.py",
    "openfoam": "run_openfoam_qualification.py",
    "su2": "run_su2_qualification.py",
    "cad": "run_cad_roundtrip_matrix.py",
    "cuda": "run_gpu_qualification.py",
    "endurance_24h": "run_endurance_24h.py",
    "endurance_72h": "run_endurance_72h.py",
    "second_machine": "verify_second_machine.py",
}


def fingerprint() -> dict[str, str]:
    values = {
        "hostname": platform.node(), "platform": platform.platform(), "machine": platform.machine(),
        "python": sys.version, "operator": os.environ.get("USER", "unknown"),
    }
    values["sha256"] = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("track", choices=sorted(DRIVERS))
    parser.add_argument("--sm35-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-real-execution", action="store_true")
    parser.add_argument("driver_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.authorize_real_execution:
        raise SystemExit("real external execution requires --authorize-real-execution")
    root = args.sm35_root.resolve(strict=True)
    driver = (root / "tools" / DRIVERS[args.track]).resolve(strict=True)
    if root != driver and root not in driver.parents:
        raise SystemExit("driver path escaped the SM35 tree")
    started_utc = datetime.now(timezone.utc).isoformat(); monotonic = time.monotonic()
    command = [sys.executable, str(driver), *args.driver_args]
    run = subprocess.run(command, cwd=root, text=True, capture_output=True)
    receipt = {
        "format": "SM36_PHYSICAL_CAMPAIGN_RECEIPT_V1", "track": args.track,
        "state": "PASS" if run.returncode == 0 else "FAIL", "claim_level": "TESTED",
        "started_utc": started_utc, "ended_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_monotonic_seconds": time.monotonic() - monotonic, "exit_code": run.returncode,
        "command": command, "environment": fingerprint(), "stdout": run.stdout, "stderr": run.stderr,
        "independent_review_state": "BLOCKED", "limitations": ["Independent review and gate ingestion remain mandatory."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
