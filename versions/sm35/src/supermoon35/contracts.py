"""Strict SM35 receipt contracts and truth-boundary validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ValidationError(ValueError):
    """Raised when evidence violates a non-bypassable contract."""


class ExecutionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_EXECUTED = "NOT_EXECUTED"
    NONCONVERGED = "NONCONVERGED"
    BLOCKED = "BLOCKED"


class ClaimLevel(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    BENCHMARKED = "BENCHMARKED"
    STRESS_TESTED = "STRESS_TESTED"
    QUALIFIED = "QUALIFIED"
    EXTERNALLY_REPRODUCED = "EXTERNALLY_REPRODUCED"


def _finite_tree(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError(f"non-finite number at {path}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _finite_tree(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _finite_tree(item, f"{path}[{index}]")


def _timestamp(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{field_name} must be a nonempty RFC3339 timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"invalid {field_name}") from exc
    if parsed.tzinfo is None:
        raise ValidationError(f"{field_name} must include a timezone")
    return parsed


def canonical_json(value: Any) -> bytes:
    _finite_tree(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    logical_path: str
    size_bytes: int
    sha256: str

    def validate(self) -> None:
        if not IDENTIFIER.fullmatch(self.artifact_id):
            raise ValidationError("invalid artifact_id")
        if not self.logical_path or self.logical_path.startswith(("/", "\\")) or ".." in self.logical_path.replace("\\", "/").split("/"):
            raise ValidationError("artifact logical_path must be confined and relative")
        if not isinstance(self.size_bytes, int) or self.size_bytes < 0:
            raise ValidationError("artifact size must be a nonnegative integer")
        if not HEX64.fullmatch(self.sha256):
            raise ValidationError("artifact sha256 must be lowercase hex")


@dataclass(frozen=True, slots=True)
class PhysicalReceipt:
    run_id: str
    track_id: str
    status: ExecutionStatus
    claim_level: ClaimLevel
    started_utc: str
    ended_utc: str
    elapsed_monotonic_seconds: float
    environment: Mapping[str, Any]
    environment_sha256: str
    input_artifacts: tuple[Artifact, ...] = ()
    output_artifacts: tuple[Artifact, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    thresholds: Mapping[str, Any] = field(default_factory=dict)
    checks: Mapping[str, bool] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    reviewer_decision: ExecutionStatus = ExecutionStatus.BLOCKED
    format: str = "SM35_EXECUTION_RECEIPT_V1"

    def validate(self) -> None:
        if self.format != "SM35_EXECUTION_RECEIPT_V1":
            raise ValidationError("unknown receipt format")
        for name, value in (("run_id", self.run_id), ("track_id", self.track_id)):
            if not IDENTIFIER.fullmatch(value):
                raise ValidationError(f"invalid {name}")
        started = _timestamp(self.started_utc, "started_utc")
        ended = _timestamp(self.ended_utc, "ended_utc")
        if ended < started:
            raise ValidationError("ended_utc precedes started_utc")
        if not isinstance(self.elapsed_monotonic_seconds, (int, float)) or not math.isfinite(self.elapsed_monotonic_seconds) or self.elapsed_monotonic_seconds < 0:
            raise ValidationError("elapsed_monotonic_seconds must be finite and nonnegative")
        _finite_tree(self.environment, "$.environment")
        _finite_tree(self.metrics, "$.metrics")
        _finite_tree(self.thresholds, "$.thresholds")
        if sha256_json(self.environment) != self.environment_sha256:
            raise ValidationError("environment hash mismatch")
        artifacts = self.input_artifacts + self.output_artifacts
        for artifact in artifacts:
            artifact.validate()
        artifact_ids = [item.artifact_id for item in artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValidationError("duplicate artifact IDs")
        if len(self.evidence_ids) != len(set(self.evidence_ids)) or any(not IDENTIFIER.fullmatch(item) for item in self.evidence_ids):
            raise ValidationError("invalid or duplicate evidence IDs")
        if any(not isinstance(value, bool) for value in self.checks.values()):
            raise ValidationError("checks must contain booleans")
        if self.status is ExecutionStatus.PASS:
            if not self.evidence_ids or not self.checks or not all(self.checks.values()):
                raise ValidationError("PASS requires evidence and all checks true")
            if self.reviewer_decision is not ExecutionStatus.PASS:
                raise ValidationError("PASS requires reviewer PASS")
        if self.status in {ExecutionStatus.UNAVAILABLE, ExecutionStatus.NOT_EXECUTED, ExecutionStatus.BLOCKED} and self.reviewer_decision is ExecutionStatus.PASS:
            raise ValidationError("non-execution cannot produce reviewer PASS")

    def payload(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["status"] = self.status.value
        value["claim_level"] = self.claim_level.value
        value["reviewer_decision"] = self.reviewer_decision.value
        return value


def validate_receipt_mapping(payload: Mapping[str, Any]) -> PhysicalReceipt:
    required = {field.name for field in PhysicalReceipt.__dataclass_fields__.values()}
    unknown = set(payload) - required
    missing = required - set(payload)
    if unknown or missing:
        raise ValidationError(f"receipt fields mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}")
    try:
        inputs = tuple(Artifact(**item) for item in payload["input_artifacts"])
        outputs = tuple(Artifact(**item) for item in payload["output_artifacts"])
        receipt = PhysicalReceipt(
            **{
                **dict(payload),
                "status": ExecutionStatus(payload["status"]),
                "claim_level": ClaimLevel(payload["claim_level"]),
                "reviewer_decision": ExecutionStatus(payload["reviewer_decision"]),
                "input_artifacts": inputs,
                "output_artifacts": outputs,
                "limitations": tuple(payload["limitations"]),
                "evidence_ids": tuple(payload["evidence_ids"]),
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("malformed receipt") from exc
    receipt.validate()
    return receipt
