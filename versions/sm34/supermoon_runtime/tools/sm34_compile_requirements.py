#!/usr/bin/env python3
"""Compile all 200,000 SM34 prompt lines to a traceability ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon34.requirements import compile_prompt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", type=Path)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    result = compile_prompt(args.prompt, args.matrix)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

