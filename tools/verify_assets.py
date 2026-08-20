#!/usr/bin/env python3
"""Verify the immutable merged release asset or a Git LFS pointer."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path


NAME = "SUPER_MOON_36_NEW_UNIVERSE_QUALIFICATION_CANDIDATE_FULL_MERGED.txt.gz"
BYTES = 391_292_410
SHA256 = "71ac376db613c70d5cad52394f03adfcb7f2412e4c643bbb2e301e1c47473c33"
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allow-lfs-pointer", action="store_true")
    args = parser.parse_args()
    asset = args.root / "assets" / NAME
    if not asset.is_file():
        raise SystemExit(f"missing asset: {asset}")
    with asset.open("rb") as stream:
        head = stream.read(len(LFS_HEADER))
    if head == LFS_HEADER:
        if args.allow_lfs_pointer:
            print("asset=LFS_POINTER_ALLOWED")
            return 0
        raise SystemExit("asset is only a Git LFS pointer; run git lfs pull")
    if asset.stat().st_size != BYTES:
        raise SystemExit(f"size mismatch: {asset.stat().st_size} != {BYTES}")
    actual = sha256(asset)
    if actual != SHA256:
        raise SystemExit(f"SHA-256 mismatch: {actual} != {SHA256}")
    with gzip.open(asset, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            pass
    print(f"asset=PASS bytes={BYTES} sha256={actual} gzip=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

