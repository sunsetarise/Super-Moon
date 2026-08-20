#!/usr/bin/env python3
"""Deterministic adversarial fuzzing of SM36 parsers and numerical contracts."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon36.contracts import ValidationError, finite_tree, safe_logical_path
from supermoon36.framing import encode_frame, parse_frames
from supermoon36.physical import GridPoint, conservation_balance, grid_convergence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=360035)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 100:
        raise SystemExit("at least 100 trials are required")
    rng = random.Random(args.seed)
    failures: list[dict[str, object]] = []
    categories = {"path": 0, "frame": 0, "finite": 0, "gci": 0, "conservation": 0}
    for trial in range(args.trials):
        category = tuple(categories)[trial % len(categories)]; categories[category] += 1
        try:
            if category == "path":
                unsafe = rng.choice(("../x", "/root/x", "a\\b", "", "a/../../b"))
                try:
                    safe_logical_path(unsafe)
                except ValidationError:
                    continue
                raise AssertionError("unsafe path accepted")
            if category == "frame":
                frame = bytearray(encode_frame(f"fuzz/{trial}.bin", rng.randbytes(rng.randint(1, 96))))
                body_start = frame.index(b"\n") + 1
                body_end = frame.index(b"\n", body_start)
                index = rng.randrange(body_start, body_end); frame[index] ^= rng.randint(1, 255)
                try:
                    tuple(parse_frames(BytesIO(frame)))
                except (ValidationError, UnicodeDecodeError):
                    continue
                raise AssertionError("corrupted frame accepted")
            if category == "finite":
                try:
                    finite_tree({"x": rng.choice((math.nan, math.inf, -math.inf))})
                except ValidationError:
                    continue
                raise AssertionError("non-finite tree accepted")
            if category == "gci":
                points = [GridPoint(1.0, 1.0), GridPoint(1.0, 2.0), GridPoint(4.0, 3.0)]
                try:
                    grid_convergence(points)
                except ValidationError:
                    continue
                raise AssertionError("invalid refinement grid accepted")
            try:
                conservation_balance(1.0, 1.0, 0.0, 0.0, rng.choice((0.0, -1.0, math.nan)))
            except ValidationError:
                continue
            raise AssertionError("invalid conservation scale accepted")
        except Exception as exc:
            failures.append({"trial": trial, "category": category, "error": f"{type(exc).__name__}: {exc}"})
    payload = {
        "format": "SM36_FUZZ_CAMPAIGN_V1", "seed": args.seed, "trials": args.trials,
        "categories": categories, "failures": failures, "failure_count": len(failures),
        "passed": not failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
