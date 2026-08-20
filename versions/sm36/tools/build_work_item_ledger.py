#!/usr/bin/env python3
"""Build the complete 15,000-row pending operational obligation ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from supermoon36.registry import MethodologyRegistry
from supermoon36.workitems import pending_work_item, write_work_items


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024): digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--timestamp", default="2026-08-20T00:00:00+00:00")
    args = parser.parse_args()
    registry = MethodologyRegistry.read_jsonl_gz(args.registry)
    prompt_sha = sha(args.prompt); registry_sha = sha(args.registry)
    rows = tuple(pending_work_item(row, prompt_sha256=prompt_sha, registry_sha256=registry_sha, completion_timestamp=args.timestamp) for row in registry.records)
    write_work_items(args.output, rows)
    summary = {
        "format": "SM36_METHODOLOGY_WORK_ITEM_SUMMARY_V1", "records": len(rows),
        "states": {state: sum(row.result_state.value == state for row in rows) for state in ("BLOCKED", "NOT_EXECUTED")},
        "ledger_sha256": sha(args.output), "prompt_sha256": prompt_sha, "registry_sha256": registry_sha,
        "qualification_credit": False,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
