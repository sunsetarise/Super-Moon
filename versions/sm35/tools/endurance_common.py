"""Real-wall-clock endurance driver shared by exact 24h and 72h entrypoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time


def run(hours: int, output: Path, checkpoint: Path, heartbeat_seconds: float = 60.0) -> int:
    if hours not in {24, 72}:
        raise ValueError("only exact 24h or 72h profiles are permitted")
    start = time.monotonic()
    deadline = start + hours * 3600
    sequence = 0
    previous = "0" * 64
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as telemetry:
        while time.monotonic() < deadline:
            payload = {"sequence": sequence, "elapsed_monotonic_seconds": time.monotonic() - start, "previous": previous}
            previous = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            payload["chain_sha256"] = previous
            telemetry.write(json.dumps(payload, sort_keys=True) + "\n"); telemetry.flush()
            checkpoint.write_text(json.dumps(payload, sort_keys=True) + "\n")
            sequence += 1
            time.sleep(min(heartbeat_seconds, max(0.0, deadline - time.monotonic())))
    return 0
