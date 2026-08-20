"""Physical capability detection and mandatory execution-matrix contracts."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
from typing import Mapping, Sequence

from .contracts import ClaimLevel, ExecutionStatus, PhysicalReceipt, ValidationError, sha256_json


TRACK_TO_COMMANDS: dict[str, tuple[str, ...]] = {
    "petsc_mpi": ("mpiexec", "mpirun"),
    "openfoam": ("foamRun", "checkMesh"),
    "su2": ("SU2_CFD", "SU2_CFD_AD"),
    "hpc": ("sbatch", "sacct", "sstat"),
    "gpu": ("nvidia-smi", "nvcc"),
    "containers": ("apptainer", "spack"),
}
TRACK_TO_MODULES: dict[str, tuple[str, ...]] = {
    "petsc_mpi": ("petsc4py", "mpi4py"),
    "cad": ("cadquery", "OCP"),
    "gpu": ("cupy",),
}


@dataclass(frozen=True, slots=True)
class Capability:
    track_id: str
    available: bool
    commands: Mapping[str, str | None]
    modules: Mapping[str, bool]
    reason: str


def detect_capability(track_id: str) -> Capability:
    if track_id not in set(TRACK_TO_COMMANDS) | set(TRACK_TO_MODULES):
        raise ValidationError(f"unknown physical track: {track_id}")
    commands = {name: shutil.which(name) for name in TRACK_TO_COMMANDS.get(track_id, ())}
    modules = {name: importlib.util.find_spec(name) is not None for name in TRACK_TO_MODULES.get(track_id, ())}
    components = list(commands.values()) + list(modules.values())
    available = bool(components) and all(bool(item) for item in components)
    reason = "all required local components detected" if available else "one or more required local components unavailable"
    return Capability(track_id, available, commands, modules, reason)


def capability_matrix() -> tuple[Capability, ...]:
    return tuple(detect_capability(track_id) for track_id in sorted(set(TRACK_TO_COMMANDS) | set(TRACK_TO_MODULES)))


def unavailable_receipt(track_id: str, environment: Mapping[str, object], limitation: str, *, timestamp: str) -> PhysicalReceipt:
    receipt = PhysicalReceipt(
        run_id=f"sm35-{track_id}-unavailable",
        track_id=track_id,
        status=ExecutionStatus.UNAVAILABLE,
        claim_level=ClaimLevel.IMPLEMENTED,
        started_utc=timestamp,
        ended_utc=timestamp,
        elapsed_monotonic_seconds=0.0,
        environment=environment,
        environment_sha256=sha256_json(environment),
        checks={"physical_execution_completed": False},
        limitations=(limitation,),
        reviewer_decision=ExecutionStatus.BLOCKED,
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True, slots=True)
class PetscRankResult:
    ranks: int
    nodes: int
    terminal_states: tuple[str, ...]
    ownership_ranges: tuple[tuple[int, int], ...]
    residual: float
    evidence_ids: tuple[str, ...]

    def validate(self) -> None:
        if self.ranks not in {1, 2, 3, 4, 8} or self.nodes < 1:
            raise ValidationError("invalid PETSc rank or node count")
        if len(self.terminal_states) != self.ranks or set(self.terminal_states) != {"PASS"}:
            raise ValidationError("all ranks must agree on PASS")
        if len(self.ownership_ranges) != self.ranks:
            raise ValidationError("ownership range missing for a rank")
        ordered = sorted(self.ownership_ranges)
        if ordered[0][0] != 0 or any(left[1] != right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValidationError("ownership ranges are not a contiguous partition")
        if not 0 <= self.residual <= 1e-8 or not self.evidence_ids:
            raise ValidationError("PETSc residual/evidence requirement failed")


def validate_petsc_matrix(results: Sequence[PetscRankResult]) -> bool:
    if len(results) != 5 or {item.ranks for item in results} != {1, 2, 3, 4, 8}:
        raise ValidationError("rank matrix requires exactly 1/2/3/4/8")
    for result in results:
        result.validate()
    if not any(item.nodes >= 2 and item.ranks in {4, 8} for item in results):
        raise ValidationError("rank matrix lacks a 4/8-rank multi-node run")
    return True


@dataclass(frozen=True, slots=True)
class ExternalCommandPolicy:
    executables: tuple[Path, ...]
    work_roots: tuple[Path, ...]
    timeout_seconds: float = 3600.0
    output_limit_bytes: int = 16 * 1024 * 1024

    def validate(self) -> None:
        if not self.executables or not self.work_roots:
            raise ValidationError("command policy requires executable and work-root allowlists")
        if self.timeout_seconds <= 0 or self.output_limit_bytes <= 0:
            raise ValidationError("command policy limits must be positive")


def execute_authorized(policy: ExternalCommandPolicy, executable: Path, argv: Sequence[str], cwd: Path, *, authorized: bool) -> subprocess.CompletedProcess[bytes]:
    policy.validate()
    if not authorized:
        raise ValidationError("explicit external execution authorization required")
    resolved_executable = executable.resolve(strict=True)
    allowed_executables = {item.resolve(strict=True) for item in policy.executables}
    if resolved_executable not in allowed_executables:
        raise ValidationError("executable is outside the allowlist")
    resolved_cwd = cwd.resolve(strict=True)
    allowed_roots = tuple(item.resolve(strict=True) for item in policy.work_roots)
    if not any(resolved_cwd == root or root in resolved_cwd.parents for root in allowed_roots):
        raise ValidationError("working directory is outside the allowlist")
    safe_environment = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL", "OMP_NUM_THREADS"}}
    completed = subprocess.run(
        [str(resolved_executable), *argv], cwd=resolved_cwd, env=safe_environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=policy.timeout_seconds,
        check=False, shell=False,
    )
    if len(completed.stdout) + len(completed.stderr) > policy.output_limit_bytes:
        raise ValidationError("external command output exceeded configured limit")
    return completed
