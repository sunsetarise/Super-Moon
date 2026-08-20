#!/usr/bin/env python3
"""Stream and attest the complete immutable SM35 compressed/decompressed baseline."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def compressed_hashes(path: Path) -> dict[str, object]:
    sha256 = hashlib.sha256(); sha512 = hashlib.sha512(); total = 0
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            total += len(chunk); sha256.update(chunk); sha512.update(chunk)
    return {"size_bytes": total, "sha256": sha256.hexdigest(), "sha512": sha512.hexdigest()}


def decompressed_hashes(path: Path) -> dict[str, object]:
    sha256 = hashlib.sha256(); sha512 = hashlib.sha512(); total = 0; newlines = 0; tail = b""
    with gzip.open(path, "rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            total += len(chunk); newlines += chunk.count(b"\n"); sha256.update(chunk); sha512.update(chunk)
            tail = (tail + chunk)[-4096:]
    return {
        "size_bytes": total, "newline_count": newlines, "sha256": sha256.hexdigest(),
        "sha512": sha512.hexdigest(), "terminal_sm35_marker_present": b"SM35_ADDITIVE_LAYER_END" in tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--part", type=Path, action="append", default=[])
    parser.add_argument("--inventory-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = args.baseline.resolve(strict=True); compressed = compressed_hashes(baseline)
    parts = []
    concatenated_sha = hashlib.sha256(); concatenated_size = 0
    for path in args.part:
        resolved = path.resolve(strict=True); row = compressed_hashes(resolved); row["name"] = resolved.name; parts.append(row)
        with resolved.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024): concatenated_sha.update(chunk); concatenated_size += len(chunk)
    inventory = []
    if args.inventory_root:
        root = args.inventory_root.resolve(strict=True)
        for path in sorted(item for item in root.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
            row = compressed_hashes(path); row["path"] = path.relative_to(root).as_posix(); inventory.append(row)
    payload = {
        "format": "SM36_SM35_BASELINE_PRESERVATION_INPUT_V1", "compressed": compressed,
        "decompressed": decompressed_hashes(baseline), "parts": parts,
        "parts_concatenated": {"size_bytes": concatenated_size, "sha256": concatenated_sha.hexdigest(), "matches_baseline": bool(parts) and concatenated_size == compressed["size_bytes"] and concatenated_sha.hexdigest() == compressed["sha256"]},
        "reconstructed_inventory": inventory, "reconstructed_file_count": len(inventory),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["decompressed"]["terminal_sm35_marker_present"] and (not parts or payload["parts_concatenated"]["matches_baseline"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
