#!/usr/bin/env python3
"""Create a concatenated-gzip SM35 release while preserving SM34 exactly."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil


HEADER = b"\n================================================================================\nSM35_ADDITIVE_LAYER_BEGIN\nrelease_name=SUPER MOON 35 NEW UNIVERSE QUALIFICATION CANDIDATE\nrelease_state=BLOCKED_PENDING_REAL_EXECUTION\nformat=SM35_STREAM_FRAMES_V1\n================================================================================\n"
END = b"SM35_ADDITIVE_LAYER_END\n"


def digest(path: Path) -> tuple[int, str]:
    total = 0
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total += len(chunk); sha.update(chunk)
    return total, sha.hexdigest()


def write_frame(output: gzip.GzipFile, logical_path: str, source: Path) -> dict[str, object]:
    if logical_path.startswith("/") or ".." in Path(logical_path).parts:
        raise ValueError("unsafe logical path")
    size, sha256 = digest(source)
    output.write(f"<<<SM35_FILE path={logical_path} bytes={size} sha256={sha256} encoding=base64>>>\n".encode())
    with source.open("rb") as stream:
        while chunk := stream.read(3 * 1024 * 1024):
            output.write(base64.b64encode(chunk))
    output.write(b"\n<<<END_SM35_FILE>>>\n")
    return {"path": logical_path, "size_bytes": size, "sha256": sha256}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--layer-root", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--promptstudio-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.baseline, args.output)
    rows: list[dict[str, object]] = []
    with args.output.open("ab") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as output:
            output.write(HEADER)
            for source in sorted(item for item in args.layer_root.rglob("*") if item.is_file() and "__pycache__" not in item.parts and not item.name.endswith((".pyc", ".pyo"))):
                rows.append(write_frame(output, f"sm35/{source.relative_to(args.layer_root).as_posix()}", source))
            rows.append(write_frame(output, "sm35/spec/SUPER_MOON_34_TO_35_MASTER_PROMPT.txt", args.prompt))
            rows.append(write_frame(output, "inherited_promptstudio/SuperMoon34_NewUniverse_PromptStudio_SETUP_FIXED_V2.7z", args.promptstudio_archive))
            manifest = json.dumps({"format": "SM35_FRAME_MANIFEST_V1", "files": rows}, sort_keys=True, separators=(",", ":")).encode()
            temp_manifest = args.output.parent / ".SM35_FRAME_MANIFEST.json"
            temp_manifest.write_bytes(manifest + b"\n")
            try:
                write_frame(output, "sm35/evidence/SM35_FRAME_MANIFEST.json", temp_manifest)
            finally:
                temp_manifest.unlink(missing_ok=True)
            output.write(END)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
