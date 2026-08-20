#!/usr/bin/env python3
"""Build a deterministic source archive while streaming the large asset from parts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


ASSET_NAME = "SUPER_MOON_36_NEW_UNIVERSE_QUALIFICATION_CANDIDATE_FULL_MERGED.txt.gz"
MANIFEST_PATH = Path("manifests/GITHUB_SOURCE_MANIFEST.json")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_parts(parts: list[Path], expected_bytes: int, expected_sha256: str) -> None:
    digest = hashlib.sha256()
    total = 0
    for part in parts:
        if not part.is_file():
            raise SystemExit(f"missing asset part: {part}")
        with part.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
                total += len(chunk)
    if total != expected_bytes or digest.hexdigest() != expected_sha256:
        raise SystemExit(
            f"asset parts failed verification: bytes={total}/{expected_bytes} "
            f"sha256={digest.hexdigest()}/{expected_sha256}"
        )


class PartsReader(io.RawIOBase):
    def __init__(self, parts: list[Path]):
        self._parts = iter(parts)
        self._stream = None

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if size == 0:
            return b""
        output = bytearray()
        target = size if size >= 0 else None
        while target is None or len(output) < target:
            if self._stream is None:
                try:
                    self._stream = next(self._parts).open("rb")
                except StopIteration:
                    break
            request = -1 if target is None else target - len(output)
            chunk = self._stream.read(request)
            if chunk:
                output.extend(chunk)
            else:
                self._stream.close()
                self._stream = None
        return bytes(output)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
        super().close()


def normalized(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("asset_part_prefix", type=Path)
    parser.add_argument("--asset-part-count", type=int, required=True)
    parser.add_argument("--asset-bytes", type=int, required=True)
    parser.add_argument("--asset-sha256", required=True)
    args = parser.parse_args()

    root = args.repository.resolve()
    archive = args.archive.resolve()
    asset_relative = Path("assets") / ASSET_NAME
    manifest = root / MANIFEST_PATH
    parts = [Path(f"{args.asset_part_prefix}.{index:03d}") for index in range(1, args.asset_part_count + 1)]
    verify_parts(parts, args.asset_bytes, args.asset_sha256)

    records = []
    source_paths = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            if path.is_symlink():
                raise SystemExit(f"symlinks are not permitted: {path}")
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if relative in (asset_relative, MANIFEST_PATH):
            continue
        source_paths.append((relative, path))
        records.append({"path": relative.as_posix(), "bytes": path.stat().st_size, "sha256": hash_file(path)})
    records.append({"path": asset_relative.as_posix(), "bytes": args.asset_bytes, "sha256": args.asset_sha256})
    records.sort(key=lambda row: row["path"])
    payload = {
        "format": "SUPER_MOON_36_GITHUB_SOURCE_MANIFEST_V1",
        "release_state": "BLOCKED_PENDING_REAL_EXECUTION",
        "file_count_excluding_manifest": len(records),
        "total_bytes_excluding_manifest": sum(int(record["bytes"]) for record in records),
        "files": records,
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    source_paths.append((MANIFEST_PATH, manifest))
    source_paths.sort(key=lambda item: item[0].as_posix())

    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=1, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as output:
                for relative, path in source_paths:
                    arcname = f"{root.name}/{relative.as_posix()}"
                    info = normalized(output.gettarinfo(str(path), arcname=arcname))
                    with path.open("rb") as stream:
                        output.addfile(info, stream)
                asset_info = tarfile.TarInfo(f"{root.name}/{asset_relative.as_posix()}")
                asset_info.size = args.asset_bytes
                asset_info.mode = 0o644
                normalized(asset_info)
                reader = PartsReader(parts)
                try:
                    output.addfile(asset_info, reader)
                finally:
                    reader.close()

    print(
        json.dumps(
            {
                "archive": str(archive),
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": hash_file(archive),
                "source_files_excluding_manifest": len(records),
                "asset_bytes": args.asset_bytes,
                "asset_sha256": args.asset_sha256,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
