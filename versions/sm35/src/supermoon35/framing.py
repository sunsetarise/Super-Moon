"""Safe additive text framing and exact reconstruction primitives."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import BinaryIO, Iterable

from .contracts import ValidationError


BEGIN = re.compile(r"^<<<SM35_FILE path=(.+) bytes=([0-9]+) sha256=([0-9a-f]{64}) encoding=(raw|base64)>>>$")
END = "<<<END_SM35_FILE>>>"


@dataclass(frozen=True, slots=True)
class FramedFile:
    path: str
    data: bytes
    sha256: str
    encoding: str


def safe_path(value: str) -> PurePosixPath:
    candidate = PurePosixPath(value)
    if not value or candidate.is_absolute() or ".." in candidate.parts or "" in candidate.parts:
        raise ValidationError("unsafe framed path")
    return candidate


def encode_file(path: str, payload: bytes, *, force_base64: bool = False) -> bytes:
    safe_path(path)
    digest = hashlib.sha256(payload).hexdigest()
    raw_safe = not force_base64 and b"\x00" not in payload and b"\n" not in payload and b"\r" not in payload and payload.decode("utf-8", errors="ignore").encode("utf-8") == payload
    encoding = "raw" if raw_safe else "base64"
    body = payload if raw_safe else base64.b64encode(payload)
    header = f"<<<SM35_FILE path={path} bytes={len(payload)} sha256={digest} encoding={encoding}>>>\n".encode()
    return header + body + b"\n" + END.encode() + b"\n"


def parse_frames(stream: BinaryIO) -> Iterable[FramedFile]:
    seen: set[str] = set()
    while True:
        line = stream.readline()
        if not line:
            return
        decoded = line.rstrip(b"\r\n").decode("utf-8", errors="strict")
        if not decoded:
            continue
        match = BEGIN.fullmatch(decoded)
        if not match:
            raise ValidationError("malformed frame header")
        path, expected_size, expected_hash, encoding = match.groups()
        safe_path(path)
        if path in seen:
            raise ValidationError("duplicate framed path")
        seen.add(path)
        body = stream.readline().rstrip(b"\r\n")
        end = stream.readline().rstrip(b"\r\n").decode("utf-8", errors="strict")
        if end != END:
            raise ValidationError("missing frame terminator")
        try:
            payload = body if encoding == "raw" else base64.b64decode(body, validate=True)
        except ValueError as exc:
            raise ValidationError("invalid base64 frame") from exc
        if len(payload) != int(expected_size) or hashlib.sha256(payload).hexdigest() != expected_hash:
            raise ValidationError("framed file length or hash mismatch")
        yield FramedFile(path, payload, expected_hash, encoding)


def reconstruct(stream: BinaryIO, root: Path) -> tuple[Path, ...]:
    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()
    outputs: list[Path] = []
    for frame in parse_frames(stream):
        target = (resolved_root / frame.path).resolve()
        if resolved_root != target and resolved_root not in target.parents:
            raise ValidationError("framed path escaped output root")
        if target.exists():
            raise ValidationError("refusing to overwrite reconstructed path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(frame.data)
        outputs.append(target)
    return tuple(outputs)
