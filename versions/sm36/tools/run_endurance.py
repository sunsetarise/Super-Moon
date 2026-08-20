#!/usr/bin/env python3
"""Real-wall-clock 24/72-hour heartbeat producer with no shortened mode."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import time

from pathlib import Path as _Path
import sys
ROOT = _Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.endurance import Heartbeat


def open_handles() -> int:
    directory = Path("/proc/self/fd")
    return len(list(directory.iterdir())) if directory.exists() else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_hours", type=int, choices=(24, 72))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--heartbeat-seconds", type=float, default=60.0)
    args = parser.parse_args()
    if not 1 <= args.heartbeat_seconds <= 120:
        raise ValueError("heartbeat interval must be within 1..120 seconds")
    start = time.monotonic(); deadline = start + args.profile_hours * 3600; previous = "0" * 64; sequence = 0
    args.output.parent.mkdir(parents=True, exist_ok=True); args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as stream:
        while time.monotonic() < deadline:
            body = {
                "sequence": sequence, "elapsed_monotonic_seconds": time.monotonic() - start,
                "resident_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "open_handles": open_handles(), "progress_counter": sequence + 1, "previous_sha256": previous,
            }
            heartbeat = Heartbeat(**body, chain_sha256=hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
            heartbeat.validate(); previous = heartbeat.chain_sha256
            row = json.dumps(asdict(heartbeat), sort_keys=True, separators=(",", ":")) + "\n"
            stream.write(row); stream.flush(); args.checkpoint.write_text(row, encoding="utf-8")
            sequence += 1; time.sleep(min(args.heartbeat_seconds, max(0.0, deadline - time.monotonic())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

