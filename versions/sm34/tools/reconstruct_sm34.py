from __future__ import annotations

import argparse
import gzip
import hashlib
import re
from pathlib import Path, PurePosixPath


LAYER_MARKER = b'<<<SM34_ADDITIVE_LAYER format="SM34_LENGTH_PREFIXED_V1" release="SUPER_MOON_34_NEW_UNIVERSE">>>'
FILE_HEADER = re.compile(
    rb'^<<<SM34_FILE path="(?P<path>[^"]+)" sha256="(?P<sha>[0-9a-f]{64})" bytes="(?P<size>\d+)">>>$'
)
END_FILE = b"<<<END_SM34_FILE>>>"
END_LAYER = b"<<<END_SM34_ADDITIVE_LAYER>>>"


def _safe_target(root: Path, encoded_path: str) -> Path:
    relative = PurePosixPath(encoded_path)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"unsafe embedded path: {encoded_path!r}")
    target = root.joinpath(*relative.parts).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"embedded path escapes output root: {encoded_path!r}")
    return target


def reconstruct(source: Path, output: Path, *, verify_only: bool = False) -> dict:
    source = source.resolve()
    output = output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output.mkdir(parents=True, exist_ok=True)

    found_layer = False
    files = 0
    total_bytes = 0
    manifest_hash = hashlib.sha256()

    with gzip.open(source, "rb") as stream:
        for raw_line in stream:
            if raw_line.rstrip(b"\r\n") == LAYER_MARKER:
                found_layer = True
                break
        if not found_layer:
            raise ValueError("SM34 additive layer marker was not found")

        while True:
            raw_line = stream.readline()
            if not raw_line:
                raise EOFError("SM34 additive layer ended without a closing marker")
            line = raw_line.rstrip(b"\r\n")
            if not line:
                continue
            if line == END_LAYER:
                break

            match = FILE_HEADER.fullmatch(line)
            if not match:
                raise ValueError(f"unexpected SM34 framing record: {line[:160]!r}")

            encoded_path = match.group("path").decode("utf-8")
            expected_sha = match.group("sha").decode("ascii")
            expected_size = int(match.group("size"))
            payload = stream.read(expected_size)
            if len(payload) != expected_size:
                raise EOFError(f"truncated SM34 payload: {encoded_path}")
            actual_sha = hashlib.sha256(payload).hexdigest()
            if actual_sha != expected_sha:
                raise ValueError(f"SHA-256 mismatch for {encoded_path}: {actual_sha} != {expected_sha}")

            closing = stream.readline().rstrip(b"\r\n")
            while not closing:
                closing = stream.readline().rstrip(b"\r\n")
            if closing != END_FILE:
                raise ValueError(f"missing SM34 file terminator after {encoded_path}")

            target = _safe_target(output, encoded_path)
            if verify_only:
                if not target.is_file() or target.stat().st_size != expected_size:
                    raise ValueError(f"missing or wrong-sized reconstructed file: {target}")
                if hashlib.sha256(target.read_bytes()).hexdigest() != expected_sha:
                    raise ValueError(f"reconstructed file hash mismatch: {target}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)

            manifest_hash.update(encoded_path.encode("utf-8") + b"\0")
            manifest_hash.update(expected_sha.encode("ascii") + b"\0")
            manifest_hash.update(str(expected_size).encode("ascii") + b"\n")
            files += 1
            total_bytes += expected_size

    return {
        "format": "SM34_RECONSTRUCTION_RECEIPT_V1",
        "source": str(source),
        "output": str(output),
        "verified_only": verify_only,
        "files": files,
        "payload_bytes": total_bytes,
        "manifest_sha256": manifest_hash.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruct the length-prefixed Super Moon 34 additive layer.")
    parser.add_argument("source", type=Path, help="Canonical Super Moon 34 .txt.gz corpus")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "supermoon_runtime")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(reconstruct(args.source, args.output, verify_only=args.verify_only))


if __name__ == "__main__":
    main()
