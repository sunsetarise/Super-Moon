#!/usr/bin/env python3
"""Generate an equal-work local benchmark receipt without HPC overclaim."""

from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon34.performance import BenchmarkSuite


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rng = np.random.default_rng(34)
    matrix = rng.standard_normal((256, 256))
    vector = rng.standard_normal(256)
    receipt = BenchmarkSuite().measure(lambda: matrix @ vector, work_units=256 * 256 * 2, warmups=3, repetitions=15)
    payload = {"format": "SM34_LOCAL_BENCHMARK_V1", "claim": "LOCAL_CPU_REFERENCE_ONLY", "receipt": asdict(receipt)}
    payload["receipt"]["status"] = receipt.status.value
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

