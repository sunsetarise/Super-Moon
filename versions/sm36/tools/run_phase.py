#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.methodology import ExecutionContext, MethodologyExecutor, phase_completion
from supermoon36.registry import MethodologyRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("phase_id", choices=tuple(f"P{i:02d}" for i in range(1, 7)))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-execution", action="store_true")
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--reviewer")
    args = parser.parse_args()
    registry = MethodologyRegistry.read_jsonl_gz(args.registry)
    context = ExecutionContext(json.loads(args.evidence.read_text()), args.physical_execution, bool(args.reviewer), args.reviewer, args.authorize)
    results = MethodologyExecutor().evaluate_phase(registry.phase(args.phase_id), context)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as stream:
            for result in results:
                stream.write(json.dumps(result.payload(), sort_keys=True, separators=(",", ":")).encode() + b"\n")
    completion = phase_completion(results)
    print(json.dumps({"phase": args.phase_id, "results": len(results), "completion": completion}, sort_keys=True))
    return 0 if completion == 1.0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
