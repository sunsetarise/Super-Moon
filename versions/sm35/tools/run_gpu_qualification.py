#!/usr/bin/env python3
"""Execute synchronized real-CUDA CuPy parity and timing checks."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from tool_common import detect_capability, unavailable, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--elements", type=int, default=1_000_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capability = detect_capability("gpu")
    if not capability.available:
        return unavailable("gpu", args.output, "CUDA tooling and CuPy unavailable")
    if not args.authorize:
        return unavailable("gpu", args.output, "real CUDA execution requires explicit authorization")
    import cupy as cp
    import numpy as np
    device = cp.cuda.Device()
    properties = cp.cuda.runtime.getDeviceProperties(device.id)
    cpu = np.linspace(0, 1, args.elements, dtype=np.float64)
    start = time.perf_counter()
    gpu = cp.asarray(cpu)
    transfer_seconds = time.perf_counter() - start
    event_start, event_end = cp.cuda.Event(), cp.cuda.Event()
    event_start.record()
    output = cp.sin(gpu) ** 2 + cp.cos(gpu) ** 2
    event_end.record(); event_end.synchronize()
    kernel_ms = cp.cuda.get_elapsed_time(event_start, event_end)
    actual = cp.asnumpy(output)
    error = float(np.max(np.abs(actual - 1.0)))
    write_json(args.output, {"format": "SM35_CUDA_RUN_V1", "device_id": device.id, "device_name": properties["name"].decode(), "elements": args.elements, "transfer_seconds": transfer_seconds, "kernel_ms": kernel_ms, "max_error": error})
    return 0 if error <= 1e-12 else 2


if __name__ == "__main__":
    raise SystemExit(main())
