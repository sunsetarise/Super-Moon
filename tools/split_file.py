#!/usr/bin/env python3
"""Split a file into exact-size numeric parts and emit an integrity manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--part-bytes", type=int, default=80_000_000)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.part_bytes <= 0:
        raise SystemExit("part size must be positive")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    base = args.source.name
    parts = []
    full_hash = hashlib.sha256()
    total = 0
    with args.source.open("rb") as source:
        index = 1
        while True:
            remaining = args.part_bytes
            part_path = args.output_directory / f"{base}.{index:03d}"
            part_hash = hashlib.sha256()
            part_size = 0
            with part_path.open("wb") as target:
                while remaining:
                    chunk = source.read(min(8 * 1024 * 1024, remaining))
                    if not chunk:
                        break
                    target.write(chunk)
                    part_hash.update(chunk)
                    full_hash.update(chunk)
                    part_size += len(chunk)
                    total += len(chunk)
                    remaining -= len(chunk)
            if part_size == 0:
                part_path.unlink(missing_ok=True)
                break
            parts.append({"index": index, "file": part_path.name, "bytes": part_size, "sha256": part_hash.hexdigest()})
            index += 1
    actual_source_hash = hash_file(args.source)
    if actual_source_hash != full_hash.hexdigest():
        raise SystemExit("source hash changed while splitting")
    manifest = {
        "format": "SUPER_MOON_36_80MB_SPLIT_MANIFEST_V1",
        "source_file": args.source.name,
        "source_bytes": total,
        "source_sha256": actual_source_hash,
        "part_bytes": args.part_bytes,
        "part_count": len(parts),
        "parts": parts,
        "reassemble": f"python tools/assemble_split_parts.py {base} OUTPUT --count {len(parts)} --expected-sha256 {actual_source_hash}",
    }
    manifest_path = args.manifest or args.output_directory / f"{base}_80MB_MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("source_bytes", "source_sha256", "part_count")}))
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

