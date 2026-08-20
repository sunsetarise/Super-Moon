#!/usr/bin/env python3
"""Extract and verify framed Super Moon source files from a merged gzip release."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path, PurePosixPath


HEADER = re.compile(
    rb"^<<<SM(?P<version>34|35|36)_FILE path=(?P<path>.+?) "
    rb"bytes=(?P<bytes>[0-9]+) sha256=(?P<sha>[0-9a-f]{64}) encoding=base64>>>\n?$"
)
END = re.compile(rb"^<<<END_SM(?P<version>34|35|36)_FILE>>>\n?$")


def safe_destination(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe framed path: {relative!r}")
    target = root.joinpath(*path.parts)
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError(f"framed path escapes destination: {relative!r}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    args.destination.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    seen: dict[str, str] = {}

    with gzip.open(args.release, "rb") as stream:
        while True:
            line = stream.readline()
            if not line:
                break
            match = HEADER.match(line)
            if not match:
                continue

            version = match.group("version").decode("ascii")
            relative = match.group("path").decode("utf-8")
            expected_bytes = int(match.group("bytes"))
            expected_sha = match.group("sha").decode("ascii")
            payload = stream.readline().strip()
            footer = stream.readline()
            footer_match = END.match(footer)
            if not footer_match or footer_match.group("version").decode("ascii") != version:
                raise SystemExit(f"invalid frame footer for {relative}")
            try:
                decoded = base64.b64decode(payload, validate=True)
            except ValueError as exc:
                raise SystemExit(f"invalid base64 for {relative}: {exc}") from exc
            actual_sha = hashlib.sha256(decoded).hexdigest()
            if len(decoded) != expected_bytes or actual_sha != expected_sha:
                raise SystemExit(
                    f"integrity failure for {relative}: "
                    f"bytes {len(decoded)}/{expected_bytes}, sha256 {actual_sha}/{expected_sha}"
                )
            if relative in seen and seen[relative] != actual_sha:
                raise SystemExit(f"conflicting duplicate frame: {relative}")

            target = safe_destination(args.destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(decoded)
            seen[relative] = actual_sha
            records.append(
                {
                    "version": int(version),
                    "path": relative,
                    "bytes": len(decoded),
                    "sha256": actual_sha,
                }
            )

    if not records:
        raise SystemExit("no SM34/SM35/SM36 frames found")
    summary = {
        "release": str(args.release),
        "frame_count": len(records),
        "unique_path_count": len(seen),
        "version_counts": {
            str(version): sum(1 for record in records if record["version"] == version)
            for version in (34, 35, 36)
        },
        "records": records,
    }
    manifest = args.manifest or args.destination / "RECONSTRUCTION_MANIFEST.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("frame_count", "unique_path_count", "version_counts")}))
    print(f"manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
