#!/usr/bin/env python3
"""Run local SM34 tests, probes, validation, and conservative gate decision."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon34.backends import probe_all
from supermoon34.qualification import decision_payload, unexecuted_release
from supermoon34.validation import ValidationSuite


def encode(value):
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(type(value).__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=ROOT)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "evidence" / "SM34_LOCAL_QUALIFICATION.json")
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    environment = dict(**__import__("os").environ)
    environment["PYTHONPATH"] = str(root / "src") + ((":" + environment["PYTHONPATH"]) if environment.get("PYTHONPATH") else "")
    command = [sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"]
    tests = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True, timeout=300, check=False, shell=False)
    validation = ValidationSuite().run()
    decision = unexecuted_release()
    payload = {
        "format": "SM34_LOCAL_QUALIFICATION_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "local_tests": {"return_code": tests.returncode, "stdout": tests.stdout, "stderr": tests.stderr, "passed": tests.returncode == 0},
        "validation": validation,
        "backend_probes": probe_all(),
        "release_decision": decision_payload(decision),
        "truth": "Local source/tests can pass while the 9.5 release remains blocked by mandatory physical execution.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=encode) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True, default=encode))


if __name__ == "__main__":
    main()

