#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("runbook", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    release_target = args.output / args.release.name
    runbook_target = args.output / args.runbook.name
    shutil.copy2(args.release, release_target); shutil.copy2(args.runbook, runbook_target)
    rows = []
    for path in (release_target, runbook_target):
        rows.append({"path": path.name, "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (args.output / "REPRODUCTION_MANIFEST.json").write_text(json.dumps({"format": "SM35_REPRODUCTION_BUNDLE_V1", "files": rows}, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
