#!/usr/bin/env python3
"""Union line/branch observations from reproducible coverage runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("input", type=Path, nargs="+"); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.input]
    paths = set(payloads[0]["files"])
    if any(set(payload["files"]) != paths for payload in payloads[1:]): raise SystemExit("coverage file universes differ")
    files = {}
    for path in sorted(paths):
        rows = [payload["files"][path] for payload in payloads]
        totals = {(row["summary"]["num_statements"], row["summary"]["num_branches"]) for row in rows}
        if len(totals) != 1: raise SystemExit(f"coverage source model changed: {path}")
        statements, branches = totals.pop()
        executed_lines = sorted({line for row in rows for line in row["executed_lines"]})
        missing_line_universe = {line for row in rows for line in row["missing_lines"]} | set(executed_lines)
        executed_branches = sorted({tuple(arc) for row in rows for arc in row["executed_branches"]})
        branch_universe = {tuple(arc) for row in rows for arc in row["missing_branches"]} | set(executed_branches)
        files[path] = {
            "executed_lines": executed_lines, "missing_lines": sorted(missing_line_universe - set(executed_lines)),
            "executed_branches": [list(arc) for arc in executed_branches], "missing_branches": [list(arc) for arc in sorted(branch_universe - set(executed_branches))],
            "summary": {"covered_lines": len(executed_lines), "num_statements": statements, "covered_branches": len(executed_branches), "num_branches": branches},
        }
    result = {"meta": {"tool": "SM36_COVERAGE_UNION_V1", "runs": [str(path) for path in args.input]}, "files": files, "tests": {"runs": [payload.get("tests", {}) for payload in payloads], "passed": all(payload.get("tests", {}).get("passed") for payload in payloads)}}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if result["tests"]["passed"] else 2


if __name__ == "__main__": raise SystemExit(main())
