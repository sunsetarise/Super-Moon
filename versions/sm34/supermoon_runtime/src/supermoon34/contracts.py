"""Typed, truth-preserving contracts for SM34 qualification work."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


class QualificationError(RuntimeError):
    """Base class for SM34 failures that must remain visible."""


class InvalidInput(QualificationError):
    """A caller violated a documented precondition."""


class BackendUnavailable(QualificationError):
    """A mandatory real backend is not executable in this environment."""


class EvidenceError(QualificationError):
    """Evidence is missing, malformed, inconsistent, or corrupt."""


class GateBlocked(QualificationError):
    """A mandatory release blocker remains open."""


class ExecutionStatus(str, Enum):
    """States that never collapse unavailable work into success."""

    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_EXECUTED = "NOT_EXECUTED"
    NONCONVERGED = "NONCONVERGED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"

    @property
    def successful(self) -> bool:
        return self in {type(self).PASS, type(self).PASS_WITH_LIMITATIONS}


class ClaimLevel(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    VERIFIED = "VERIFIED"
    BENCHMARKED = "BENCHMARKED"
    STRESS_TESTED = "STRESS_TESTED"
    QUALIFIED = "QUALIFIED"
    EXTERNALLY_REPRODUCED = "EXTERNALLY_REPRODUCED"

    @property
    def rank(self) -> int:
        return tuple(type(self)).index(self)


class BackendKind(str, Enum):
    PETSC_MPI = "PETSC_MPI"
    OPENFOAM = "OPENFOAM"
    SU2 = "SU2"
    OCCT_CADQUERY = "OCCT_CADQUERY"
    EXTERNAL_HPC = "EXTERNAL_HPC"
    GPU = "GPU"
    ENDURANCE = "ENDURANCE"
    SECOND_MACHINE = "SECOND_MACHINE"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True, slots=True)
class TolerancePolicy:
    """Predeclared numerical, geometric, conservation, and gradient limits."""

    absolute: float = 1e-12
    relative: float = 1e-9
    residual: float = 1e-10
    geometry: float = 1e-7
    conservation: float = 1e-6
    gradient: float = 1e-5
    statistical: float = 0.05
    physical_floor: float = 1e-14

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value) or value < 0.0:
                raise InvalidInput(f"{name} must be finite and nonnegative")

    def close(self, actual: float, expected: float, *, scale: float = 1.0) -> bool:
        values = (actual, expected, scale)
        if not all(math.isfinite(float(item)) for item in values):
            raise InvalidInput("comparison inputs must be finite")
        reference = max(self.physical_floor, abs(scale), abs(actual), abs(expected))
        return abs(actual - expected) <= self.absolute + self.relative * reference


@dataclass(frozen=True, slots=True)
class BackendProbe:
    backend: BackendKind
    available: bool
    version: str | None
    executable: str | None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    sha256: str
    size_bytes: int
    kind: str
    path: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionReceipt:
    run_id: str
    track_id: str
    status: ExecutionStatus
    started_utc: str
    ended_utc: str
    environment_sha256: str
    input_sha256: Mapping[str, str]
    output_sha256: Mapping[str, str]
    metrics: Mapping[str, float | int | str | bool | None]
    evidence_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GateDecision:
    gate_id: str
    weight: int
    fraction: float
    status: ExecutionStatus
    blocker_id: str | None
    evidence_ids: tuple[str, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        if not self.gate_id or self.weight < 0:
            raise InvalidInput("gate id and weight are required")
        if not math.isfinite(self.fraction) or not 0.0 <= self.fraction <= 1.0:
            raise InvalidInput("gate fraction must be in [0, 1]")
        if self.status is ExecutionStatus.PASS and self.fraction != 1.0:
            raise EvidenceError("PASS requires a complete gate fraction")
        if self.status is ExecutionStatus.PASS and not self.evidence_ids:
            raise EvidenceError("PASS requires linked evidence")

    @property
    def points(self) -> float:
        return self.weight * self.fraction


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    score: float
    status: ExecutionStatus
    passed: bool
    open_blockers: tuple[str, ...]
    gates: tuple[GateDecision, ...]
    evidence_graph_valid: bool
    rationale: str


def validate_identifier(value: str, name: str) -> str:
    if not value or any(character.isspace() for character in value):
        raise InvalidInput(f"{name} must be a nonempty token")
    return value


def confined_path(path: Path, roots: Iterable[Path], *, must_exist: bool = True) -> Path:
    """Resolve a path and prove it remains under an authorized root."""

    try:
        resolved = path.resolve(strict=must_exist)
        allowed = tuple(root.resolve(strict=True) for root in roots)
    except OSError as exc:
        raise InvalidInput(f"cannot resolve confined path {path}") from exc
    if not allowed or not any(resolved == root or root in resolved.parents for root in allowed):
        raise InvalidInput(f"path escapes authorized roots: {resolved}")
    return resolved

