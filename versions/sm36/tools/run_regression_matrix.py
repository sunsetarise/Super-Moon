#!/usr/bin/env python3
"""Execute inherited and additive unittest suites and emit one evidence record."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    for version in (34, 35, 36):
        parser.add_argument(f"--sm{version}-src", type=Path, required=True)
        parser.add_argument(f"--sm{version}-tests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_paths = [getattr(args, f"sm{version}_src").resolve(strict=True) for version in (36, 35, 34)]
    environment = dict(os.environ); environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in source_paths)
    rows = []
    for version in (34, 35, 36):
        tests = getattr(args, f"sm{version}_tests").resolve(strict=True)
        command = [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-p", "test*.py"]
        started = datetime.now(timezone.utc).isoformat(); monotonic = time.monotonic()
        run = subprocess.run(command, text=True, capture_output=True, env=environment)
        rows.append({
            "version": version, "command": command, "started_utc": started,
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "elapsed_monotonic_seconds": time.monotonic() - monotonic,
            "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr,
            "passed": run.returncode == 0,
        })
    payload = {"format": "SM36_REGRESSION_MATRIX_V1", "suites": rows, "passed": all(row["passed"] for row in rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
