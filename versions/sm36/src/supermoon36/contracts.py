"""Strict contracts shared by all SM36 qualification phases."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from pathlib import PurePosixPath
import re
from typing import Any, Mapping, Sequence


HEX64 = re.compile(r"^[0-9a-f]{64}$")
METHOD_ID = re.compile(r"^P0[1-6]-M(?:0[0-9]{3}|1[0-9]{3}|2[0-4][0-9]{2}|2500)$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")


class ValidationError(ValueError):
    """Raised when evidence or configuration violates a mandatory contract."""


class ResultState(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    BENCHMARKED = "BENCHMARKED"
    STRESS_TESTED = "STRESS_TESTED"
    PASS = "PASS"
    FAIL = "FAIL"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_EXECUTED = "NOT_EXECUTED"
    NONCONVERGED = "NONCONVERGED"
    BLOCKED = "BLOCKED"
    QUALIFIED = "QUALIFIED"
    EXTERNALLY_REPRODUCED = "EXTERNALLY_REPRODUCED"
    CERTIFICATION_READY = "CERTIFICATION_READY"


class ClaimLevel(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    BENCHMARKED = "BENCHMARKED"
    STRESS_TESTED = "STRESS_TESTED"
    QUALIFIED = "QUALIFIED"
    EXTERNALLY_REPRODUCED = "EXTERNALLY_REPRODUCED"
    CERTIFICATION_READY = "CERTIFICATION_READY"


def finite_tree(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError(f"non-finite value at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(f"non-string mapping key at {path}")
            finite_tree(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            finite_tree(item, f"{path}[{index}]")


def canonical_json(value: Any) -> bytes:
    finite_tree(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def timestamp(value: str, name: str = "timestamp") -> datetime:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{name} must be nonempty")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"invalid {name}") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{name} must include timezone")
    return parsed


def safe_logical_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValidationError("logical path must be nonempty POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "" in path.parts:
        raise ValidationError("logical path is not confined")
    return path


@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    logical_path: str
    size_bytes: int
    sha256: str
    media_type: str = "application/octet-stream"

    def validate(self) -> None:
        if not IDENTIFIER.fullmatch(self.artifact_id):
            raise ValidationError("invalid artifact identifier")
        safe_logical_path(self.logical_path)
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValidationError("artifact size must be nonnegative integer")
        if not HEX64.fullmatch(self.sha256):
            raise ValidationError("artifact sha256 must be lowercase hexadecimal")
        if not isinstance(self.media_type, str) or "/" not in self.media_type:
            raise ValidationError("artifact media type is invalid")


@dataclass(frozen=True, slots=True)
class MethodologyRecord:
    methodology_id: str
    phase_id: str
    technique_kernel: str
    qualification_lens: str
    objective: str
    required_evidence: str
    pass_gate: str
    failure_action: str
    claim_rule: str
    technique_binding: str
    lens_binding: str
    record_sha256: str
    format: str = "SM36_METHODOLOGY_RECORD_V1"

    def validate(self) -> None:
        if self.format != "SM36_METHODOLOGY_RECORD_V1":
            raise ValidationError("unknown methodology record format")
        if not METHOD_ID.fullmatch(self.methodology_id):
            raise ValidationError("invalid methodology ID")
        if self.phase_id != self.methodology_id[:3]:
            raise ValidationError("methodology phase mismatch")
        fields = (
            self.technique_kernel, self.qualification_lens, self.objective,
            self.required_evidence, self.pass_gate, self.failure_action,
            self.claim_rule, self.technique_binding, self.lens_binding,
        )
        if any(not isinstance(item, str) or not item.strip() for item in fields):
            raise ValidationError("methodology text fields must be nonempty")
        body = asdict(self)
        expected = body.pop("record_sha256")
        if not HEX64.fullmatch(expected) or sha256_json(body) != expected:
            raise ValidationError("methodology record hash mismatch")


@dataclass(frozen=True, slots=True)
class MethodologyResult:
    methodology_id: str
    state: ResultState
    claim_level: ClaimLevel
    started_utc: str
    ended_utc: str
    elapsed_monotonic_seconds: float
    checks: Mapping[str, bool]
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    blocker_ids: tuple[str, ...] = ()
    reviewer: str | None = None
    reviewer_state: ResultState = ResultState.BLOCKED
    format: str = "SM36_METHODOLOGY_RESULT_V1"

    def validate(self) -> None:
        if self.format != "SM36_METHODOLOGY_RESULT_V1" or not METHOD_ID.fullmatch(self.methodology_id):
            raise ValidationError("invalid methodology result identity")
        start = timestamp(self.started_utc, "started_utc")
        end = timestamp(self.ended_utc, "ended_utc")
        if end < start:
            raise ValidationError("methodology result ends before it starts")
        if not isinstance(self.elapsed_monotonic_seconds, (int, float)) or not math.isfinite(self.elapsed_monotonic_seconds) or self.elapsed_monotonic_seconds < 0:
            raise ValidationError("elapsed time must be finite and nonnegative")
        finite_tree(self.metrics)
        if any(not isinstance(value, bool) for value in self.checks.values()):
            raise ValidationError("methodology checks must be boolean")
        for collection in (self.evidence_ids, self.blocker_ids):
            if len(collection) != len(set(collection)) or any(not IDENTIFIER.fullmatch(item) for item in collection):
                raise ValidationError("invalid or duplicate evidence/blocker identifiers")
        if self.state is ResultState.PASS:
            if not self.checks or not all(self.checks.values()) or not self.evidence_ids:
                raise ValidationError("PASS requires all checks and evidence")
            if not self.reviewer or self.reviewer_state is not ResultState.PASS:
                raise ValidationError("PASS requires independent reviewer PASS")
        if self.state in {ResultState.UNAVAILABLE, ResultState.NOT_EXECUTED, ResultState.BLOCKED} and self.reviewer_state is ResultState.PASS:
            raise ValidationError("non-execution cannot receive reviewer PASS")

    def payload(self) -> dict[str, Any]:
        self.validate()
        row = asdict(self)
        row["state"] = self.state.value
        row["claim_level"] = self.claim_level.value
        row["reviewer_state"] = self.reviewer_state.value
        return row


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    run_id: str
    track_id: str
    state: ResultState
    claim_level: ClaimLevel
    started_utc: str
    ended_utc: str
    elapsed_monotonic_seconds: float
    environment: Mapping[str, Any]
    environment_sha256: str
    inputs: tuple[Artifact, ...] = ()
    outputs: tuple[Artifact, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    thresholds: Mapping[str, Any] = field(default_factory=dict)
    checks: Mapping[str, bool] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    reviewer: str | None = None
    reviewer_state: ResultState = ResultState.BLOCKED
    physical_attestation: Mapping[str, Any] = field(default_factory=dict)
    format: str = "SM36_EXECUTION_RECEIPT_V1"

    def validate(self) -> None:
        if self.format != "SM36_EXECUTION_RECEIPT_V1":
            raise ValidationError("unknown execution receipt format")
        if not IDENTIFIER.fullmatch(self.run_id) or not IDENTIFIER.fullmatch(self.track_id):
            raise ValidationError("invalid receipt identity")
        start = timestamp(self.started_utc, "started_utc")
        end = timestamp(self.ended_utc, "ended_utc")
        if end < start or not math.isfinite(self.elapsed_monotonic_seconds) or self.elapsed_monotonic_seconds < 0:
            raise ValidationError("invalid receipt timing")
        finite_tree(self.environment); finite_tree(self.metrics); finite_tree(self.thresholds); finite_tree(self.physical_attestation)
        if sha256_json(self.environment) != self.environment_sha256:
            raise ValidationError("environment fingerprint mismatch")
        artifacts = self.inputs + self.outputs
        for artifact in artifacts:
            artifact.validate()
        ids = [artifact.artifact_id for artifact in artifacts]
        if len(ids) != len(set(ids)):
            raise ValidationError("duplicate receipt artifact ID")
        if any(not isinstance(value, bool) for value in self.checks.values()):
            raise ValidationError("receipt checks must be boolean")
        if self.state is ResultState.PASS:
            if not self.checks or not all(self.checks.values()) or not self.evidence_ids:
                raise ValidationError("PASS receipt lacks checks or evidence")
            if self.reviewer_state is not ResultState.PASS or not self.reviewer:
                raise ValidationError("PASS receipt lacks independent review")
        if self.claim_level in {ClaimLevel.QUALIFIED, ClaimLevel.EXTERNALLY_REPRODUCED, ClaimLevel.CERTIFICATION_READY}:
            if self.state is not ResultState.PASS or not self.physical_attestation:
                raise ValidationError("high claim requires PASS and physical attestation")

    def payload(self) -> dict[str, Any]:
        self.validate()
        row = asdict(self)
        row["state"] = self.state.value
        row["claim_level"] = self.claim_level.value
        row["reviewer_state"] = self.reviewer_state.value
        return row


def validate_result_mapping(payload: Mapping[str, Any]) -> MethodologyResult:
    expected = set(MethodologyResult.__dataclass_fields__)
    if set(payload) != expected:
        raise ValidationError("methodology result fields mismatch")
    try:
        item = MethodologyResult(
            **{
                **dict(payload),
                "state": ResultState(payload["state"]),
                "claim_level": ClaimLevel(payload["claim_level"]),
                "reviewer_state": ResultState(payload["reviewer_state"]),
                "evidence_ids": tuple(payload["evidence_ids"]),
                "limitations": tuple(payload["limitations"]),
                "blocker_ids": tuple(payload["blocker_ids"]),
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("malformed methodology result") from exc
    item.validate()
    return item


def unique_identifiers(values: Sequence[str], name: str) -> tuple[str, ...]:
    result = tuple(values)
    if len(result) != len(set(result)) or any(not IDENTIFIER.fullmatch(item) for item in result):
        raise ValidationError(f"invalid {name}")
    return result
