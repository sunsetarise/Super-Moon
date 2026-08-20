#!/usr/bin/env python3
"""Safely reconstruct and hash-verify the SM34 length-prefixed layer."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path, PurePosixPath
import re

HEADER = re.compile(rb'^<<<SM34_FILE path="([^"]+)" sha256="([0-9a-f]{64})" bytes="([0-9]+)">>>\n$')
END = b"<<<END_SM34_FILE>>>\n"


def target(root: Path, name: str) -> Path:
    logical = PurePosixPath(name)
    if logical.is_absolute() or ".." in logical.parts:
        raise ValueError(f"unsafe embedded path {name}")
    return root.joinpath(*logical.parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(args.release, "rb") as stream:
        while line := stream.readline():
            match = HEADER.match(line)
            if match is None:
                continue
            name = match.group(1).decode("utf-8")
            expected = match.group(2).decode("ascii")
            size = int(match.group(3))
            payload = stream.read(size)
            if len(payload) != size or hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError(f"corrupt embedded file {name}")
            if stream.read(1) != b"\n" or stream.readline() != END:
                raise ValueError(f"invalid framing for {name}")
            destination = target(args.output, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            count += 1
    if count == 0:
        raise ValueError("no SM34 files found")
    print(f"reconstructed={count} root={args.output}")


if __name__ == "__main__":
    main()

