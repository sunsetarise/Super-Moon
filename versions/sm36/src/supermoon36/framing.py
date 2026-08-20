"""Streaming-safe SM36 file framing and confined reconstruction primitives."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import BinaryIO, Iterator

from .contracts import ValidationError, safe_logical_path


BEGIN = re.compile(rb"^<<<SM36_FILE path=(.+) bytes=([0-9]+) sha256=([0-9a-f]{64}) encoding=base64>>>\n$")
END = b"<<<END_SM36_FILE>>>\n"


@dataclass(frozen=True, slots=True)
class Frame:
    path: str
    size_bytes: int
    sha256: str
    data: bytes


def encode_frame(path: str, data: bytes) -> bytes:
    safe_logical_path(path)
    digest = hashlib.sha256(data).hexdigest()
    return f"<<<SM36_FILE path={path} bytes={len(data)} sha256={digest} encoding=base64>>>\n".encode() + base64.b64encode(data) + b"\n" + END


def parse_frames(stream: BinaryIO) -> Iterator[Frame]:
    seen: set[str] = set()
    while True:
        line = stream.readline()
        if not line:
            return
        if not line.strip():
            continue
        match = BEGIN.fullmatch(line)
        if not match:
            raise ValidationError("malformed SM36 frame header")
        path = match.group(1).decode("utf-8"); safe_logical_path(path)
        if path in seen:
            raise ValidationError("duplicate SM36 frame path")
        seen.add(path)
        size = int(match.group(2)); expected = match.group(3).decode("ascii")
        body = stream.readline().rstrip(b"\n")
        if stream.readline() != END:
            raise ValidationError("malformed SM36 frame terminator")
        try:
            data = base64.b64decode(body, validate=True)
        except ValueError as exc:
            raise ValidationError("invalid SM36 base64 payload") from exc
        if base64.b64encode(data) != body:
            raise ValidationError("non-canonical SM36 base64 payload")
        if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
            raise ValidationError("SM36 frame length/hash mismatch")
        yield Frame(path, size, expected, data)


def reconstruct(stream: BinaryIO, root: Path) -> tuple[Path, ...]:
    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve(); outputs = []
    for frame in parse_frames(stream):
        target = (resolved_root / frame.path).resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise ValidationError("SM36 frame escaped reconstruction root")
        if target.exists():
            raise ValidationError("refusing to overwrite reconstructed SM36 file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(frame.data); outputs.append(target)
    return tuple(outputs)
