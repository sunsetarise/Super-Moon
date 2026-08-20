#!/usr/bin/env python3
"""Append a deterministic SM36 gzip member while preserving SM35 exactly."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


HEADER = b"\n================================================================================\nSM36_ADDITIVE_LAYER_BEGIN\nrelease_name=SUPER MOON 36 NEW UNIVERSE QUALIFICATION CANDIDATE\nrelease_state=BLOCKED_PENDING_REAL_EXECUTION\nformat=SM36_STREAM_FRAMES_V1\nmethodologies=15000\n================================================================================\n"
END = b"SM36_ADDITIVE_LAYER_END\n"


def digest(path: Path) -> tuple[int, str]:
    total = 0; sha = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total += len(chunk); sha.update(chunk)
    return total, sha.hexdigest()


def write_frame(output: gzip.GzipFile, logical_path: str, source: Path) -> dict[str, object]:
    if logical_path.startswith("/") or ".." in Path(logical_path).parts:
        raise ValueError("unsafe logical path")
    size, sha256 = digest(source)
    output.write(f"<<<SM36_FILE path={logical_path} bytes={size} sha256={sha256} encoding=base64>>>\n".encode())
    with source.open("rb") as stream:
        while chunk := stream.read(3 * 1024 * 1024):
            output.write(base64.b64encode(chunk))
    output.write(b"\n<<<END_SM36_FILE>>>\n")
    return {"path": logical_path, "size_bytes": size, "sha256": sha256}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--layer-root", type=Path, required=True)
    parser.add_argument("--master-prompt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = args.baseline.resolve(strict=True); layer = args.layer_root.resolve(strict=True); prompt = args.master_prompt.resolve(strict=True)
    output_path = args.output.resolve()
    if output_path == baseline:
        raise ValueError("output must not overwrite the SM35 baseline")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(baseline, args.output)
    rows = []; seen: set[str] = set()
    prompt_logical_path = "sm36/spec/SUPER_MOON_35_TO_36_15000_ADVANCED_QUALIFICATION_METHODOLOGIES_MASTER_PROMPT.txt"
    with args.output.open("ab") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as output:
            output.write(HEADER)
            for source in sorted(item for item in layer.rglob("*") if item.is_file() and "__pycache__" not in item.parts and not item.name.endswith((".pyc", ".pyo"))):
                logical_path = f"sm36/{source.relative_to(layer).as_posix()}"
                if logical_path == prompt_logical_path:
                    continue
                if logical_path in seen:
                    raise ValueError(f"duplicate package path: {logical_path}")
                seen.add(logical_path); rows.append(write_frame(output, logical_path, source))
            seen.add(prompt_logical_path); rows.append(write_frame(output, prompt_logical_path, prompt))
            manifest = {"format": "SM36_FRAME_MANIFEST_V1", "baseline_sm35": {"size_bytes": baseline.stat().st_size, "sha256": digest(baseline)[1]}, "files": rows}
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=args.output.parent, prefix="sm36-manifest-", suffix=".json") as stream:
                json.dump(manifest, stream, separators=(",", ":"), sort_keys=True); stream.write("\n"); manifest_path = Path(stream.name)
            try:
                write_frame(output, "sm36/evidence/SM36_FRAME_MANIFEST.json", manifest_path)
            finally:
                manifest_path.unlink(missing_ok=True)
            output.write(END)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
