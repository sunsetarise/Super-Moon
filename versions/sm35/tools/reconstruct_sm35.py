#!/usr/bin/env python3
"""Safely reconstruct the SM35 additive gzip member with streaming base64."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import math
from pathlib import Path
import re


FRAME = re.compile(rb"^<<<SM35_FILE path=(.+) bytes=([0-9]+) sha256=([0-9a-f]{64}) encoding=base64>>>\n$")


def safe_target(root: Path, logical: str) -> Path:
    if logical.startswith("/") or ".." in Path(logical).parts:
        raise ValueError("unsafe frame path")
    target = (root / logical).resolve()
    resolved = root.resolve()
    if resolved != target and resolved not in target.parents:
        raise ValueError("frame escaped output root")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("--baseline-compressed-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with args.release.open("rb") as raw:
        raw.seek(args.baseline_compressed_bytes)
        with gzip.GzipFile(fileobj=raw, mode="rb") as layer:
            while (line := layer.readline()) and not line.startswith(b"<<<SM35_FILE "):
                pass
            while line.startswith(b"<<<SM35_FILE "):
                match = FRAME.fullmatch(line)
                if not match:
                    raise ValueError("malformed frame")
                logical = match.group(1).decode("utf-8")
                size = int(match.group(2)); expected = match.group(3).decode()
                if logical in seen:
                    raise ValueError("duplicate frame path")
                seen.add(logical)
                target = safe_target(args.output, logical)
                if target.exists():
                    raise ValueError("refusing to overwrite reconstructed file")
                target.parent.mkdir(parents=True, exist_ok=True)
                encoded_remaining = 4 * math.ceil(size / 3)
                sha = hashlib.sha256(); written = 0
                with target.open("wb") as output:
                    while encoded_remaining:
                        count = min(encoded_remaining, 4 * 1024 * 1024)
                        count -= count % 4
                        block = layer.read(count)
                        if len(block) != count:
                            raise ValueError("truncated base64 body")
                        decoded = base64.b64decode(block, validate=True)
                        output.write(decoded); sha.update(decoded); written += len(decoded)
                        encoded_remaining -= count
                if layer.read(1) != b"\n" or layer.readline() != b"<<<END_SM35_FILE>>>\n":
                    raise ValueError("malformed frame terminator")
                if written != size or sha.hexdigest() != expected:
                    raise ValueError("frame size or hash mismatch")
                line = layer.readline()
    print(f"reconstructed_files={len(seen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
