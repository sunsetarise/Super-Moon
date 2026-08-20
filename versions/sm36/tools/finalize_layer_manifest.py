#!/usr/bin/env python3
"""Hash every final SM36 layer file except self-referential package manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXCLUDED = {"SM36_LAYER_MANIFEST.json", "SM36_FRAME_MANIFEST.json"}


def hashes(path: Path) -> tuple[int, str, str]:
    total = 0; sha256 = hashlib.sha256(); sha512 = hashlib.sha512()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total += len(chunk); sha256.update(chunk); sha512.update(chunk)
    return total, sha256.hexdigest(), sha512.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    root = args.root.resolve(strict=True); rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts and not item.name.endswith((".pyc", ".pyo")) and item.name not in EXCLUDED):
        size, sha256, sha512 = hashes(path)
        rows.append({"path": path.relative_to(root).as_posix(), "size_bytes": size, "sha256": sha256, "sha512": sha512})
    payload = {"format": "SM36_LAYER_MANIFEST_V1", "file_count": len(rows), "files": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__": raise SystemExit(main())
