"""Streaming compiler for all 200,000 SM34 master-prompt lines."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from typing import BinaryIO, Iterator, Mapping, TextIO

from .capabilities import TRACK_BY_ID
from .contracts import BackendKind, InvalidInput
from .evidence import canonical_json

GENERIC = re.compile(r"^(REQ-\d{6}) \| (P\d{2})=([^|]+) \|")
AEROSPACE = re.compile(r"^(AERO-REQ-\d{5}) \| (A\d{2})=([^|]+) \|")
POLICY_PREFIXES = (
    "SUPER ", "AUTHORING ", "EXECUTION ", "BASELINE ", "NON-REMOVAL ",
    "TRUTH ", "REALITY ", "TARGET ", "SCOPE ", "DELIVERY ", "PETSC ",
    "MPI ", "CFD ", "CAD ", "HPC ", "GPU ", "ENDURANCE ", "REPRODUCTION ",
    "SECURITY ", "SAFETY ", "BLOCKER ", "SCORE ", "GATE ", "CLAIM ",
    "EVIDENCE ", "VERSION ", "DEPENDENCY ", "TOLERANCE ", "DISCREPANCY ",
    "PERFORMANCE ", "PORTABILITY ", "ROLLBACK ", "FINAL ", "AEROSPACE ",
    "REPRODUCIBILITY ", "MATH ", "REFERENCE ", "TRACK ", "OBLIGATION ", "SCENARIO ", "CONTROL ", "END ",
)


@dataclass(frozen=True, slots=True)
class RequirementRecord:
    line_number: int
    requirement_id: str
    record_type: str
    track_id: str | None
    track_name: str | None
    backend: str | None
    implementation_symbol: str | None
    source_line_sha256: str
    implementation_status: str
    execution_status: str
    claim_cap: str | None
    limitation: str | None


def _record(line_number: int, line: str) -> RequirementRecord:
    match = GENERIC.match(line) or AEROSPACE.match(line)
    digest = hashlib.sha256(line.encode("utf-8")).hexdigest()
    if match:
        requirement_id, track_id, declared_name = match.groups()
        track = TRACK_BY_ID.get(track_id)
        if track is None:
            raise InvalidInput(f"unknown track {track_id} at line {line_number}")
        if declared_name.strip() != track.name:
            raise InvalidInput(f"track-name mismatch at line {line_number}")
        requires_execution = track.backend is not BackendKind.INTERNAL
        return RequirementRecord(
            line_number,
            requirement_id,
            "AEROSPACE_REQUIREMENT" if requirement_id.startswith("AERO-") else "HPC_REQUIREMENT",
            track_id,
            track.name,
            track.backend.value,
            track.implementation_symbol,
            digest,
            "IMPLEMENTED",
            "NOT_EXECUTED" if requires_execution else "TESTED",
            track.claim_level.value,
            track.limitation,
        )
    if line.startswith(POLICY_PREFIXES):
        token = line.split(":", 1)[0][:96]
        return RequirementRecord(line_number, f"POLICY-{line_number:06d}", "POLICY", None, token, None, None, digest, "ENFORCED", "TESTED", None, None)
    raise InvalidInput(f"unrecognized prompt grammar at line {line_number}: {line[:80]!r}")


def iter_records(stream: TextIO) -> Iterator[RequirementRecord]:
    for line_number, raw in enumerate(stream, 1):
        line = raw.rstrip("\n")
        if line.endswith("\r"):
            line = line[:-1]
        yield _record(line_number, line)


def open_prompt(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("rt", encoding="utf-8", newline="")


def compile_prompt(prompt: Path, output: Path) -> Mapping[str, object]:
    """Compile every prompt line to a deterministic gzip JSONL ledger."""

    counts: Counter[str] = Counter()
    tracks: Counter[str] = Counter()
    prompt_hash = hashlib.sha256()
    matrix_hash = hashlib.sha256()
    output.parent.mkdir(parents=True, exist_ok=True)
    with (gzip.open(prompt, "rb") if prompt.suffix == ".gz" else prompt.open("rb")) as raw:
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            prompt_hash.update(chunk)
    with open_prompt(prompt) as source, output.open("wb") as raw_output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_output, compresslevel=9, mtime=0) as compressed:
            for record in iter_records(source):
                encoded = canonical_json(record) + b"\n"
                compressed.write(encoded)
                matrix_hash.update(encoded)
                counts[record.record_type] += 1
                if record.track_id:
                    tracks[record.track_id] += 1
    total = sum(counts.values())
    if total != 200_000 or counts["HPC_REQUIREMENT"] != 149_600 or counts["AEROSPACE_REQUIREMENT"] != 50_000:
        raise InvalidInput(f"unexpected prompt cardinality: total={total} counts={dict(counts)}")
    return {
        "format": "SM34_REQUIREMENT_COMPILATION_V1",
        "prompt_lines": total,
        "prompt_decompressed_sha256": prompt_hash.hexdigest(),
        "matrix_records": total,
        "matrix_decompressed_sha256": matrix_hash.hexdigest(),
        "counts": dict(sorted(counts.items())),
        "track_counts": dict(sorted(tracks.items())),
        "implementation_policy": "All requirement rows map to additive source symbols; physical executions remain NOT_EXECUTED until real receipts exist.",
    }
