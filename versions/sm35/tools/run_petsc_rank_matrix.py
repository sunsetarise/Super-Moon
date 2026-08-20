#!/usr/bin/env python3
"""Launch real PETSc worker jobs at 1/2/3/4/8 ranks when explicitly authorized."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import shutil
import subprocess

from tool_common import detect_capability, unavailable, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=Path, default=Path(__file__).with_name("petsc_poisson_worker.py"))
    args = parser.parse_args()
    capability = detect_capability("petsc_mpi")
    launcher = shutil.which("mpiexec") or shutil.which("mpirun")
    if not capability.available or not launcher:
        return unavailable("petsc_mpi", args.output, "petsc4py/mpi4py or an MPI launcher is unavailable")
    if not args.authorize:
        return unavailable("petsc_mpi", args.output, "physical launch detected but explicit authorization was not supplied")
    jobs = []
    for ranks in (1, 2, 3, 4, 8):
        completed = subprocess.run([launcher, "-n", str(ranks), "python3", str(args.worker)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3600, check=False, shell=False)
        jobs.append({"ranks": ranks, "returncode": completed.returncode, "stdout": completed.stdout.decode(errors="replace"), "stderr": completed.stderr.decode(errors="replace")})
    write_json(args.output, {"format": "SM35_PETSC_RANK_MATRIX_V1", "capability": asdict(capability), "jobs": jobs, "multi_node_required_separately": True})
    return 0 if all(item["returncode"] == 0 for item in jobs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
