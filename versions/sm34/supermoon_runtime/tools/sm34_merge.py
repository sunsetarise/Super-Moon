#!/usr/bin/env python3
"""Append a deterministic SM34 gzip member without changing SM33 bytes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import shutil


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sm33_gzip", type=Path)
    parser.add_argument("sm34_layer", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.sm33_gzip.open("rb") as source, args.output.open("wb") as target:
        shutil.copyfileobj(source, target, 1024 * 1024)
    with args.output.open("ab") as target, gzip.GzipFile(filename="", mode="wb", fileobj=target, compresslevel=9, mtime=0) as member, args.sm34_layer.open("rb") as layer:
        shutil.copyfileobj(layer, member, 1024 * 1024)
    print(f"output={args.output} bytes={args.output.stat().st_size} sha256={digest(args.output)}")


if __name__ == "__main__":
    main()

