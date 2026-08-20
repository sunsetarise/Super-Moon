#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.methodology import ExecutionContext, MethodologyExecutor
from supermoon36.registry import MethodologyRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("methodology_id")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--physical-execution", action="store_true")
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--reviewer")
    args = parser.parse_args()
    registry = MethodologyRegistry.read_jsonl_gz(args.registry)
    context = ExecutionContext(
        json.loads(args.evidence.read_text(encoding="utf-8")), args.physical_execution,
        bool(args.reviewer), args.reviewer, args.authorize,
    )
    result = MethodologyExecutor().execute(registry.get(args.methodology_id), context)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result.state.value == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

