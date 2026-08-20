#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from supermoon36.registry import MethodologyRegistry, parse_master_prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    registry = MethodologyRegistry(parse_master_prompt(args.prompt))
    registry.write_jsonl_gz(args.output)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(registry.summary(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(registry.summary(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

