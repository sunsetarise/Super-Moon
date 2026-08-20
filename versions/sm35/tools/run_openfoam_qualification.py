#!/usr/bin/env python3
"""Run checkMesh then the installed OpenFOAM solver on an authorized case."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

from tool_common import detect_capability, unavailable, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capability = detect_capability("openfoam")
    if not capability.available:
        return unavailable("openfoam", args.output, "OpenFOAM foamRun/checkMesh unavailable")
    if not args.authorize:
        return unavailable("openfoam", args.output, "OpenFOAM execution requires explicit authorization")
    case = args.case.resolve(strict=True)
    results = []
    for argv in ([shutil.which("checkMesh"), "-case", str(case)], [shutil.which("foamRun"), "-case", str(case)]):
        run = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=24 * 3600, check=False, shell=False)
        results.append({"argv": argv, "returncode": run.returncode, "stdout": run.stdout.decode(errors="replace"), "stderr": run.stderr.decode(errors="replace")})
        if run.returncode:
            break
    write_json(args.output, {"format": "SM35_OPENFOAM_RUN_V1", "results": results})
    return 0 if len(results) == 2 and all(row["returncode"] == 0 for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
