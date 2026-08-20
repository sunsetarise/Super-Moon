#!/usr/bin/env python3
"""Run real SU2 primal and optional adjoint configurations."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

from tool_common import detect_capability, unavailable, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("primal", type=Path)
    parser.add_argument("--adjoint", type=Path)
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capability = detect_capability("su2")
    if not capability.available:
        return unavailable("su2", args.output, "SU2_CFD/SU2_CFD_AD unavailable")
    if not args.authorize:
        return unavailable("su2", args.output, "SU2 execution requires explicit authorization")
    jobs = [("SU2_CFD", args.primal)] + ([ ("SU2_CFD_AD", args.adjoint) ] if args.adjoint else [])
    results = []
    for executable, config in jobs:
        run = subprocess.run([shutil.which(executable), str(config.resolve(strict=True))], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=24 * 3600, check=False, shell=False)
        results.append({"executable": executable, "returncode": run.returncode, "stdout": run.stdout.decode(errors="replace"), "stderr": run.stderr.decode(errors="replace")})
    write_json(args.output, {"format": "SM35_SU2_RUN_V1", "results": results, "adjoint_required_for_qualification": True})
    return 0 if args.adjoint and all(row["returncode"] == 0 for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
