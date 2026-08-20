#!/usr/bin/env python3
"""Reassemble deterministic numeric split parts without loading them in memory."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix", type=Path, help="Path before .001")
    parser.add_argument("output", type=Path)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()

    parts = [Path(f"{args.prefix}.{index:03d}") for index in range(1, args.count + 1)]
    missing = [str(path) for path in parts if not path.is_file()]
    if missing:
        raise SystemExit("Missing parts: " + ", ".join(missing))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256()
    byte_count = 0
    with args.output.open("wb") as target:
        for part in parts:
            with part.open("rb") as source:
                for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    target.write(chunk)
                    sha256.update(chunk)
                    byte_count += len(chunk)

    actual = sha256.hexdigest()
    if args.expected_sha256 and actual.lower() != args.expected_sha256.lower():
        args.output.unlink(missing_ok=True)
        raise SystemExit(f"SHA-256 mismatch: expected {args.expected_sha256}, got {actual}")
    print(f"assembled={args.output}")
    print(f"bytes={byte_count}")
    print(f"sha256={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
