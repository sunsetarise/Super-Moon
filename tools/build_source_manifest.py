#!/usr/bin/env python3
"""Build a deterministic repository file manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path == output or ".git" in path.relative_to(root).parts:
            continue
        relative = path.relative_to(root).as_posix()
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "format": "SUPER_MOON_36_GITHUB_SOURCE_MANIFEST_V1",
        "release_state": "BLOCKED_PENDING_REAL_EXECUTION",
        "file_count_excluding_manifest": len(records),
        "total_bytes_excluding_manifest": sum(record["bytes"] for record in records),
        "files": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("file_count_excluding_manifest", "total_bytes_excluding_manifest")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

