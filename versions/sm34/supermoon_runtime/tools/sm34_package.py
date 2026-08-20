#!/usr/bin/env python3
"""Build a deterministic length-prefixed SM34 additive layer."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import BinaryIO, Iterable


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def copy_payload(source: BinaryIO, output: BinaryIO) -> None:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        output.write(chunk)


def add_file(output: BinaryIO, logical_path: str, source: Path) -> dict[str, object]:
    size = source.stat().st_size
    sha = digest(source)
    output.write(f'<<<SM34_FILE path="{logical_path}" sha256="{sha}" bytes="{size}">>>\n'.encode("utf-8"))
    with source.open("rb") as stream:
        copy_payload(stream, output)
    output.write(b"\n<<<END_SM34_FILE>>>\n")
    return {"path": logical_path, "bytes": size, "sha256": sha}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("prompt_gzip", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    prompt = args.prompt_gzip.resolve(strict=True)
    output = args.output.resolve()
    paths = sorted(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    rows: list[dict[str, object]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        stream.write(b'\n<<<SM34_ADDITIVE_LAYER format="SM34_LENGTH_PREFIXED_V1" release="SUPER_MOON_34_NEW_UNIVERSE">>>\n')
        for path in paths:
            rows.append(add_file(stream, path.relative_to(root).as_posix(), path))
        rows.append(add_file(stream, "spec/SUPER_MOON_34_200000_LINE_MASTER_PROMPT.txt.gz", prompt))
        index_payload = json.dumps(rows, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        index_sha = hashlib.sha256(index_payload).hexdigest()
        stream.write(f'<<<SM34_FILE path="evidence/SM34_LAYER_FILE_INDEX.json" sha256="{index_sha}" bytes="{len(index_payload)}">>>\n'.encode("utf-8"))
        stream.write(index_payload)
        stream.write(b"\n<<<END_SM34_FILE>>>\n<<<END_SM34_ADDITIVE_LAYER>>>\n")
    print(json.dumps({"format": "SM34_LAYER_BUILD_V1", "files": len(rows) + 1, "payload_files": rows, "layer_bytes": output.stat().st_size, "layer_sha256": digest(output)}, indent=2))


if __name__ == "__main__":
    main()

