"""Parse, validate, index, and serialize all 15,000 SM36 methodologies."""

from __future__ import annotations

from dataclasses import asdict, replace
import gzip
import json
from pathlib import Path
import re
from typing import Iterable, Iterator, Mapping

from .contracts import MethodologyRecord, ValidationError, sha256_json


HEADER = re.compile(r"^\[(P0[1-6]-M[0-9]{4})\] (.+) x (.+)$")
FIELD = re.compile(r"^  ([A-Z ]+): (.*)$")
EXPECTED_LABELS = (
    "TECHNIQUE", "EXECUTION LENS", "PHASE OBJECTIVE", "REQUIRED EVIDENCE",
    "PASS GATE", "FAILURE ACTION", "CLAIM RULE",
)
PHASE_BINDINGS = {
    "P01": "coverage",
    "P02": "hpc",
    "P03": "physical",
    "P04": "endurance",
    "P05": "industrial",
    "P06": "certification",
}


def slug(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not compact:
        raise ValidationError("cannot bind empty methodology label")
    return compact


def _build_record(methodology_id: str, technique_name: str, lens_name: str, fields: Mapping[str, str]) -> MethodologyRecord:
    phase_id = methodology_id[:3]
    base = MethodologyRecord(
        methodology_id=methodology_id,
        phase_id=phase_id,
        technique_kernel=technique_name,
        qualification_lens=lens_name,
        objective=fields["PHASE OBJECTIVE"].removesuffix("."),
        required_evidence=fields["REQUIRED EVIDENCE"].removesuffix("."),
        pass_gate=fields["PASS GATE"].removesuffix("."),
        failure_action=fields["FAILURE ACTION"].removesuffix("."),
        claim_rule=fields["CLAIM RULE"].removesuffix("."),
        technique_binding=f"{PHASE_BINDINGS[phase_id]}:{slug(technique_name)}",
        lens_binding=f"evidence:{slug(lens_name)}",
        record_sha256="0" * 64,
    )
    body = asdict(base); body.pop("record_sha256")
    record = replace(base, record_sha256=sha256_json(body))
    record.validate()
    return record


def parse_master_prompt(path: Path) -> tuple[MethodologyRecord, ...]:
    records: list[MethodologyRecord] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        match = HEADER.fullmatch(lines[index])
        if not match:
            index += 1
            continue
        method_id, technique, lens = match.groups()
        if index + 7 >= len(lines):
            raise ValidationError(f"truncated methodology {method_id}")
        fields: dict[str, str] = {}
        for offset, label in enumerate(EXPECTED_LABELS, start=1):
            field_match = FIELD.fullmatch(lines[index + offset])
            if not field_match or field_match.group(1) != label:
                raise ValidationError(f"malformed {label} for {method_id}")
            fields[label] = field_match.group(2)
        records.append(_build_record(method_id, technique, lens, fields))
        index += 8
    validate_registry(records)
    return tuple(records)


def validate_registry(records: Iterable[MethodologyRecord]) -> bool:
    rows = tuple(records)
    if len(rows) != 15000:
        raise ValidationError(f"registry must contain 15000 records, got {len(rows)}")
    identifiers = [row.methodology_id for row in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValidationError("duplicate methodology ID")
    for row in rows:
        row.validate()
    for phase_number in range(1, 7):
        phase_id = f"P{phase_number:02d}"
        phase_rows = [row for row in rows if row.phase_id == phase_id]
        expected = [f"{phase_id}-M{index:04d}" for index in range(1, 2501)]
        if len(phase_rows) != 2500 or [row.methodology_id for row in phase_rows] != expected:
            raise ValidationError(f"{phase_id} sequence/count mismatch")
        if len({row.technique_kernel for row in phase_rows}) != 50:
            raise ValidationError(f"{phase_id} must bind 50 technique kernels")
        if len({row.qualification_lens for row in phase_rows}) != 50:
            raise ValidationError(f"{phase_id} must bind 50 evidence lenses")
    return True


class MethodologyRegistry:
    def __init__(self, records: Iterable[MethodologyRecord]):
        self.records = tuple(records)
        validate_registry(self.records)
        self._lookup = {row.methodology_id: row for row in self.records}

    def get(self, methodology_id: str) -> MethodologyRecord:
        try:
            return self._lookup[methodology_id]
        except KeyError as exc:
            raise ValidationError("unknown methodology ID") from exc

    def phase(self, phase_id: str) -> tuple[MethodologyRecord, ...]:
        if phase_id not in PHASE_BINDINGS:
            raise ValidationError("unknown phase ID")
        return tuple(row for row in self.records if row.phase_id == phase_id)

    def techniques(self, phase_id: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(row.technique_kernel for row in self.phase(phase_id)))

    def lenses(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(row.qualification_lens for row in self.records))

    def summary(self) -> dict[str, object]:
        return {
            "format": "SM36_METHODOLOGY_REGISTRY_SUMMARY_V1",
            "records": len(self.records),
            "unique_technique_bindings": len({row.technique_binding for row in self.records}),
            "unique_lens_bindings": len({row.lens_binding for row in self.records}),
            "phases": {phase: len(self.phase(phase)) for phase in PHASE_BINDINGS},
            "registry_sha256": sha256_json([row.record_sha256 for row in self.records]),
        }

    def write_jsonl_gz(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as stream:
                for record in self.records:
                    stream.write(json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")

    @classmethod
    def read_jsonl_gz(cls, path: Path) -> "MethodologyRegistry":
        records = []
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                for line in stream:
                    payload = json.loads(line)
                    records.append(MethodologyRecord(**payload))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
            raise ValidationError("malformed methodology registry file") from exc
        return cls(records)


def stream_jsonl_gz(path: Path) -> Iterator[MethodologyRecord]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            record = MethodologyRecord(**json.loads(line))
            record.validate()
            yield record

