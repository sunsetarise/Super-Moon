#!/usr/bin/env python3
"""Probe physical qualification backends without turning detection into credit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.physical import capability_matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [asdict(row) for row in capability_matrix()]
    payload = {
        "format": "SM36_PHYSICAL_CAPABILITY_PROBE_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version, "platform": platform.platform(), "machine": platform.machine()},
        "capabilities": rows,
        "qualification_credit": False,
        "truth_boundary": "Detection and installation are not physical execution or qualification.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

