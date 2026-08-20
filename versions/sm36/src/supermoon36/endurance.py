"""Authenticated endurance telemetry and independent reproduction verification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from .contracts import ValidationError, canonical_json


@dataclass(frozen=True, slots=True)
class Heartbeat:
    sequence: int
    elapsed_monotonic_seconds: float
    resident_bytes: int
    open_handles: int
    progress_counter: int
    previous_sha256: str
    chain_sha256: str

    def body(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "elapsed_monotonic_seconds": self.elapsed_monotonic_seconds,
            "resident_bytes": self.resident_bytes,
            "open_handles": self.open_handles,
            "progress_counter": self.progress_counter,
            "previous_sha256": self.previous_sha256,
        }

    def validate(self) -> None:
        if not isinstance(self.sequence, int) or self.sequence < 0 or not math.isfinite(self.elapsed_monotonic_seconds) or self.elapsed_monotonic_seconds < 0:
            raise ValidationError("invalid heartbeat sequence/time")
        if any(not isinstance(value, int) or value < 0 for value in (self.resident_bytes, self.open_handles, self.progress_counter)):
            raise ValidationError("invalid heartbeat resource/progress counter")
        expected = hashlib.sha256(canonical_json(self.body())).hexdigest()
        if self.chain_sha256 != expected:
            raise ValidationError("heartbeat hash mismatch")


@dataclass(frozen=True, slots=True)
class EnduranceDecision:
    profile_hours: int
    elapsed_seconds: float
    chain_valid: bool
    max_gap_seconds: float
    memory_growth_fraction: float
    handle_growth: int
    progress_monotonic: bool
    recovery_drills: int
    passed: bool


def validate_heartbeat_chain(rows: Sequence[Heartbeat]) -> bool:
    if len(rows) < 2:
        raise ValidationError("endurance requires at least two heartbeats")
    previous = "0" * 64
    last_elapsed = -1.0
    for index, row in enumerate(rows):
        row.validate()
        if row.sequence != index or row.previous_sha256 != previous or row.elapsed_monotonic_seconds <= last_elapsed:
            raise ValidationError("heartbeat chain order/discontinuity failure")
        previous = row.chain_sha256; last_elapsed = row.elapsed_monotonic_seconds
    return True


def assess_endurance(rows: Sequence[Heartbeat], profile_hours: int, recovery_drills: int) -> EnduranceDecision:
    if profile_hours not in {24, 72}:
        raise ValidationError("profile must be exactly 24 or 72 hours")
    chain = validate_heartbeat_chain(rows)
    elapsed = rows[-1].elapsed_monotonic_seconds - rows[0].elapsed_monotonic_seconds
    gaps = [right.elapsed_monotonic_seconds - left.elapsed_monotonic_seconds for left, right in zip(rows, rows[1:])]
    max_gap = max(gaps)
    initial_memory = max(rows[0].resident_bytes, 1)
    memory_growth = (rows[-1].resident_bytes - rows[0].resident_bytes) / initial_memory
    handle_growth = rows[-1].open_handles - rows[0].open_handles
    progress = all(right.progress_counter > left.progress_counter for left, right in zip(rows, rows[1:]))
    required_drills = 1 if profile_hours == 24 else 2
    passed = chain and elapsed >= profile_hours * 3600 and max_gap <= 120 and memory_growth <= 0.05 and handle_growth <= 2 and progress and recovery_drills >= required_drills
    return EnduranceDecision(profile_hours, elapsed, chain, max_gap, memory_growth, handle_growth, progress, recovery_drills, passed)


@dataclass(frozen=True, slots=True)
class ReproductionReceipt:
    first_machine_fingerprint: str
    second_machine_fingerprint: str
    first_operator_fingerprint: str
    second_operator_fingerprint: str
    first_location: str
    second_location: str
    clean_workspace: bool
    released_artifacts_only: bool
    output_comparison_passed: bool
    environment_delta_reviewed: bool
    evidence_ids: tuple[str, ...]

    def passes(self) -> bool:
        strings = (
            self.first_machine_fingerprint, self.second_machine_fingerprint,
            self.first_operator_fingerprint, self.second_operator_fingerprint,
            self.first_location, self.second_location,
        )
        if any(not isinstance(value, str) or not value for value in strings):
            raise ValidationError("reproduction identities must be nonempty")
        return all((
            self.first_machine_fingerprint != self.second_machine_fingerprint,
            self.first_operator_fingerprint != self.second_operator_fingerprint,
            self.clean_workspace, self.released_artifacts_only,
            self.output_comparison_passed, self.environment_delta_reviewed,
            bool(self.evidence_ids),
        ))


def heartbeat_from_mapping(payload: Mapping[str, object]) -> Heartbeat:
    try:
        return Heartbeat(**payload)
    except TypeError as exc:
        raise ValidationError("heartbeat fields mismatch") from exc

